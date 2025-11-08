"""
Rate Limiting Module for Multi-Tenant Flask Application

This module provides decorators and functions to enforce per-user rate limits on:
- API calls per minute
- Searches per hour  
- Uploads per day
- Video processing minutes per day
- Storage usage

Usage:
    from rate_limiter import rate_limit_api, rate_limit_upload, rate_limit_search
    
    @app.route('/api/something')
    @login_required
    @rate_limit_api
    def api_endpoint():
        ...
    
    @app.route('/upload')
    @login_required
    @rate_limit_upload
    def upload():
        ...
"""

from functools import wraps
from flask import jsonify, request
from flask_login import current_user
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def get_rate_limits(user_id, cursor):
    """
    Get current rate limits and usage for a user.
    
    Returns:
        dict with limits and current usage, or None if no limits found
    """
    cursor.execute("""
        SELECT 
            max_uploads_per_day,
            max_searches_per_hour,
            max_api_calls_per_minute,
            max_video_processing_minutes_per_day,
            max_storage_gb,
            uploads_today,
            searches_this_hour,
            api_calls_this_minute,
            video_minutes_today,
            storage_used_gb,
            last_daily_reset,
            last_hourly_reset,
            last_minute_reset
        FROM user_rate_limits
        WHERE user_id = :user_id
    """, {'user_id': user_id})
    
    row = cursor.fetchone()
    if not row:
        return None
    
    return {
        'max_uploads_per_day': row[0],
        'max_searches_per_hour': row[1],
        'max_api_calls_per_minute': row[2],
        'max_video_processing_minutes_per_day': row[3],
        'max_storage_gb': row[4],
        'uploads_today': row[5] or 0,
        'searches_this_hour': row[6] or 0,
        'api_calls_this_minute': row[7] or 0,
        'video_minutes_today': row[8] or 0,
        'storage_used_gb': row[9] or 0,
        'last_daily_reset': row[10],
        'last_hourly_reset': row[11],
        'last_minute_reset': row[12]
    }


def reset_counters_if_needed(user_id, limits, cursor, conn):
    """
    Reset usage counters if time windows have expired.
    
    Args:
        user_id: User ID
        limits: Dict from get_rate_limits()
        cursor: Database cursor
        conn: Database connection
        
    Returns:
        Updated limits dict
    """
    now = datetime.now()
    updates = {}
    
    # Check daily reset
    if limits['last_daily_reset']:
        time_since_daily = now - limits['last_daily_reset']
        if time_since_daily >= timedelta(days=1):
            updates['uploads_today'] = 0
            updates['video_minutes_today'] = 0
            updates['last_daily_reset'] = now
            logger.info(f"🔄 Reset daily counters for user {user_id}")
    
    # Check hourly reset
    if limits['last_hourly_reset']:
        time_since_hourly = now - limits['last_hourly_reset']
        if time_since_hourly >= timedelta(hours=1):
            updates['searches_this_hour'] = 0
            updates['last_hourly_reset'] = now
            logger.info(f"🔄 Reset hourly counters for user {user_id}")
    
    # Check minute reset
    if limits['last_minute_reset']:
        time_since_minute = now - limits['last_minute_reset']
        if time_since_minute >= timedelta(minutes=1):
            updates['api_calls_this_minute'] = 0
            updates['last_minute_reset'] = now
            logger.info(f"🔄 Reset minute counters for user {user_id}")
    
    # Apply updates if any
    if updates:
        # Build SET clause manually to avoid bind variable name issues
        set_parts = []
        bind_values = {'uid': user_id}
        
        for i, (col_name, col_value) in enumerate(updates.items()):
            param_name = f'v{i}'
            set_parts.append(f"{col_name} = :{param_name}")
            bind_values[param_name] = col_value
        
        set_clause = ', '.join(set_parts)
        sql = f"UPDATE user_rate_limits SET {set_clause} WHERE user_id = :uid"
        cursor.execute(sql, bind_values)
        conn.commit()
        
        # Update limits dict with new values
        limits.update(updates)
    
    return limits


def increment_counter(user_id, counter_name, increment_by=1, cursor=None, conn=None):
    """
    Increment a specific counter for a user.
    
    Args:
        user_id: User ID
        counter_name: One of: uploads_today, searches_this_hour, api_calls_this_minute, video_minutes_today
        increment_by: Amount to increment (default 1)
        cursor: Optional database cursor (will create if None)
        conn: Optional database connection (will create if None)
    """
    from utils.db_utils_flask_safe import get_flask_safe_connection
    
    close_conn = False
    if cursor is None:
        close_conn = True
        conn = get_flask_safe_connection()
        cursor = conn.cursor()
    
    try:
        # Build SQL without f-string to avoid Oracle bind variable confusion
        # We manually construct the SQL with validated column name
        allowed_counters = [
            'uploads_today', 
            'searches_this_hour', 
            'api_calls_this_minute', 
            'video_minutes_today', 
            'storage_used_gb'
        ]
        
        if counter_name not in allowed_counters:
            raise ValueError(f"Invalid counter name: {counter_name}")
        
        # Use string formatting for column name (safe since validated) 
        # but bind variables for values
        sql = """
            UPDATE user_rate_limits 
            SET {} = NVL({}, 0) + :incr_val
            WHERE user_id = :uid
        """.format(counter_name, counter_name)
        
        cursor.execute(sql, incr_val=increment_by, uid=user_id)
        
        conn.commit()
        logger.info(f"📊 Incremented {counter_name} for user {user_id} by {increment_by}")
    finally:
        if close_conn and conn:
            conn.close()


def log_usage(user_id, action_type, action_details=None, resource_consumed=0):
    """
    Log a user action to the usage log table.
    
    Args:
        user_id: User ID
        action_type: Type of action (upload, search, api_call, video_processing, etc.)
        action_details: Optional details string
        resource_consumed: Numeric value of resource consumed (e.g., video duration in minutes)
    """
    from utils.db_utils_flask_safe import get_flask_safe_connection
    
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get IP address
            ip_address = request.remote_addr if request else None
            
            cursor.execute("""
                INSERT INTO user_usage_log (
                    user_id, action_type, action_details, resource_consumed, ip_address
                ) VALUES (
                    :user_id, :action_type, :action_details, :resource_consumed, :ip_address
                )
            """, {
                'user_id': user_id,
                'action_type': action_type,
                'action_details': action_details,
                'resource_consumed': resource_consumed,
                'ip_address': ip_address
            })
            
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Error logging usage: {e}")


def rate_limit_api(f):
    """
    Decorator to enforce API rate limit (calls per minute).
    Apply to API endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get limits
            limits = get_rate_limits(current_user.id, cursor)
            if not limits:
                logger.warning(f"⚠️  No rate limits found for user {current_user.id}, allowing request")
                return f(*args, **kwargs)
            
            # Reset counters if needed
            limits = reset_counters_if_needed(current_user.id, limits, cursor, conn)
            
            # Check limit (NULL = unlimited)
            max_calls = limits['max_api_calls_per_minute']
            if max_calls is not None:
                current_calls = limits['api_calls_this_minute']
                
                if current_calls >= max_calls:
                    logger.warning(f"🚫 User {current_user.id} exceeded API rate limit ({current_calls}/{max_calls})")
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'message': f'API call limit: {current_calls}/{max_calls} per minute. Please wait.',
                        'retry_after': 60,
                        'limit_type': 'api_calls_per_minute'
                    }), 429
            
            # Increment counter
            increment_counter(current_user.id, 'api_calls_this_minute', cursor=cursor, conn=conn)
            
            # Log usage
            log_usage(current_user.id, 'api_call', action_details=request.path)
        
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit_search(f):
    """
    Decorator to enforce search rate limit (searches per hour).
    Apply to search endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get limits
            limits = get_rate_limits(current_user.id, cursor)
            if not limits:
                logger.warning(f"⚠️  No rate limits found for user {current_user.id}, allowing request")
                return f(*args, **kwargs)
            
            # Reset counters if needed
            limits = reset_counters_if_needed(current_user.id, limits, cursor, conn)
            
            # Check limit (NULL = unlimited)
            max_searches = limits['max_searches_per_hour']
            if max_searches is not None:
                current_searches = limits['searches_this_hour']
                
                if current_searches >= max_searches:
                    logger.warning(f"🚫 User {current_user.id} exceeded search rate limit ({current_searches}/{max_searches})")
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'message': f'Search limit: {current_searches}/{max_searches} per hour. Please wait.',
                        'retry_after': 3600,
                        'limit_type': 'searches_per_hour'
                    }), 429
            
            # Increment counter
            increment_counter(current_user.id, 'searches_this_hour', cursor=cursor, conn=conn)
            
            # Log usage
            query = request.args.get('query') or request.json.get('query') if request else None
            log_usage(current_user.id, 'search', action_details=query)
        
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit_upload(f):
    """
    Decorator to enforce upload rate limit (uploads per day).
    Apply to file upload endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get limits
            limits = get_rate_limits(current_user.id, cursor)
            if not limits:
                logger.warning(f"⚠️  No rate limits found for user {current_user.id}, allowing request")
                return f(*args, **kwargs)
            
            # Reset counters if needed
            limits = reset_counters_if_needed(current_user.id, limits, cursor, conn)
            
            # Check limit (NULL = unlimited)
            max_uploads = limits['max_uploads_per_day']
            if max_uploads is not None:
                current_uploads = limits['uploads_today']
                
                if current_uploads >= max_uploads:
                    logger.warning(f"🚫 User {current_user.id} exceeded upload rate limit ({current_uploads}/{max_uploads})")
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'message': f'Daily upload limit: {current_uploads}/{max_uploads}. Please try tomorrow.',
                        'retry_after': 86400,
                        'limit_type': 'uploads_per_day'
                    }), 429
            
            # Increment counter
            increment_counter(current_user.id, 'uploads_today', cursor=cursor, conn=conn)
            
            # Log usage
            filename = request.files.get('file').filename if request and request.files else None
            log_usage(current_user.id, 'upload', action_details=filename)
        
        return f(*args, **kwargs)
    
    return decorated_function


def check_video_processing_quota(user_id, video_duration_minutes):
    """
    Check if user has enough video processing quota remaining.
    
    Args:
        user_id: User ID
        video_duration_minutes: Duration of video to process in minutes
        
    Returns:
        tuple: (allowed: bool, message: str, current_usage: int, max_quota: int)
    """
    from utils.db_utils_flask_safe import get_flask_safe_connection
    
    with get_flask_safe_connection() as conn:
        cursor = conn.cursor()
        
        # Get limits
        limits = get_rate_limits(user_id, cursor)
        if not limits:
            return (True, "No limits configured", 0, None)
        
        # Reset counters if needed
        limits = reset_counters_if_needed(user_id, limits, cursor, conn)
        
        # Check limit (NULL = unlimited)
        max_minutes = limits['max_video_processing_minutes_per_day']
        if max_minutes is None:
            return (True, "Unlimited", limits['video_minutes_today'], None)
        
        current_minutes = limits['video_minutes_today']
        remaining = max_minutes - current_minutes
        
        if remaining < video_duration_minutes:
            message = f"Insufficient video processing quota. Need {video_duration_minutes} min, have {remaining} min remaining (Daily limit: {max_minutes} min)"
            return (False, message, current_minutes, max_minutes)
        
        return (True, "OK", current_minutes, max_minutes)


def consume_video_processing_quota(user_id, video_duration_minutes):
    """
    Consume video processing quota after successful processing.
    
    Args:
        user_id: User ID
        video_duration_minutes: Duration of processed video in minutes
    """
    increment_counter(user_id, 'video_minutes_today', increment_by=video_duration_minutes)
    log_usage(user_id, 'video_processing', resource_consumed=video_duration_minutes)
    logger.info(f"📹 User {user_id} consumed {video_duration_minutes} minutes of video processing quota")


def check_storage_quota(user_id, file_size_gb):
    """
    Check if user has enough storage quota remaining.
    
    Args:
        user_id: User ID
        file_size_gb: Size of file to upload in GB
        
    Returns:
        tuple: (allowed: bool, message: str, current_usage: float, max_quota: float)
    """
    from utils.db_utils_flask_safe import get_flask_safe_connection
    
    with get_flask_safe_connection() as conn:
        cursor = conn.cursor()
        
        # Get limits
        limits = get_rate_limits(user_id, cursor)
        if not limits:
            return (True, "No limits configured", 0, None)
        
        # Check limit (NULL = unlimited)
        max_storage = limits['max_storage_gb']
        if max_storage is None:
            return (True, "Unlimited", limits['storage_used_gb'], None)
        
        current_storage = limits['storage_used_gb']
        remaining = max_storage - current_storage
        
        if remaining < file_size_gb:
            message = f"Insufficient storage quota. Need {file_size_gb:.2f} GB, have {remaining:.2f} GB remaining (Limit: {max_storage} GB)"
            return (False, message, current_storage, max_storage)
        
        return (True, "OK", current_storage, max_storage)


def update_storage_usage(user_id, file_size_gb):
    """
    Update user's storage usage after successful upload.
    
    Args:
        user_id: User ID
        file_size_gb: Size of uploaded file in GB
    """
    from utils.db_utils_flask_safe import get_flask_safe_connection
    
    with get_flask_safe_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE user_rate_limits 
            SET storage_used_gb = NVL(storage_used_gb, 0) + :size
            WHERE user_id = :user_id
        """, {'size': file_size_gb, 'user_id': user_id})
        
        conn.commit()
        logger.info(f"💾 User {user_id} storage increased by {file_size_gb:.2f} GB")


def get_user_quota_summary(user_id):
    """
    Get a summary of user's quotas and usage for display.
    
    Args:
        user_id: User ID
        
    Returns:
        dict with quota information
    """
    from utils.db_utils_flask_safe import get_flask_safe_connection
    
    with get_flask_safe_connection() as conn:
        cursor = conn.cursor()
        
        limits = get_rate_limits(user_id, cursor)
        if not limits:
            return {'error': 'No rate limits configured'}
        
        # Reset counters if needed
        limits = reset_counters_if_needed(user_id, limits, cursor, conn)
        
        def format_limit(current, maximum):
            if maximum is None:
                return f"{current}/∞"
            percentage = (current / maximum * 100) if maximum > 0 else 0
            return f"{current}/{maximum} ({percentage:.1f}%)"
        
        return {
            'uploads': {
                'current': limits['uploads_today'],
                'max': limits['max_uploads_per_day'],
                'display': format_limit(limits['uploads_today'], limits['max_uploads_per_day']),
                'period': 'day'
            },
            'searches': {
                'current': limits['searches_this_hour'],
                'max': limits['max_searches_per_hour'],
                'display': format_limit(limits['searches_this_hour'], limits['max_searches_per_hour']),
                'period': 'hour'
            },
            'api_calls': {
                'current': limits['api_calls_this_minute'],
                'max': limits['max_api_calls_per_minute'],
                'display': format_limit(limits['api_calls_this_minute'], limits['max_api_calls_per_minute']),
                'period': 'minute'
            },
            'video_processing': {
                'current': limits['video_minutes_today'],
                'max': limits['max_video_processing_minutes_per_day'],
                'display': format_limit(limits['video_minutes_today'], limits['max_video_processing_minutes_per_day']),
                'period': 'day',
                'unit': 'minutes'
            },
            'storage': {
                'current': limits['storage_used_gb'],
                'max': limits['max_storage_gb'],
                'display': format_limit(limits['storage_used_gb'], limits['max_storage_gb']),
                'unit': 'GB'
            }
        }
