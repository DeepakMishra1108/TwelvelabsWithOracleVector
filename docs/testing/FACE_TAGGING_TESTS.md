# Face Tagging Feature - Testing Guide

## Overview
This document provides comprehensive test scenarios for the face tagging feature implementation.

**Date**: December 19, 2024  
**Status**: Ready for testing

---

## Test Environment Setup

### Prerequisites
- Production VM: ubuntu@150.136.235.189
- Application URL: https://150.136.235.189:8443
- Test users with different roles:
  - Admin user (full access)
  - Editor user (can tag own photos)
  - Viewer user (face-based filtering)

### Test Data Required
- 5-10 photos with human faces
- Photos with 1, 2, and 3+ people
- Photos with same person in different photos
- Photos without faces (landscape, objects)

---

## Test Scenario 1: Manual Face Tagging

### Test 1.1: Face Detection
**User**: Editor or Admin  
**Objective**: Verify face detection works correctly

**Steps**:
1. Login as editor/admin
2. Upload a photo with 2 people
3. Wait for upload to complete
4. Navigate to photo detail page
5. Click "Detect Faces" button
6. Verify 2 faces are detected
7. Check bounding boxes are displayed

**Expected Results**:
- ✅ "Detected 2 face(s)" message shown
- ✅ Two face cards appear with position info
- ✅ Each face has name input field and "Tag" button

**Pass Criteria**: All face detection results accurate

---

### Test 1.2: Manual Face Tagging
**User**: Editor or Admin  
**Objective**: Tag detected faces with names

**Steps**:
1. Complete Test 1.1 (detect faces)
2. In first face card, enter "Alice Smith"
3. Click "Tag" button for first face
4. Verify success message
5. Enter "Bob Johnson" for second face
6. Click "Tag" button for second face
7. Check tagged faces list

**Expected Results**:
- ✅ Success message: "Successfully tagged as 'Alice Smith'"
- ✅ Tagged faces count shows 2
- ✅ Both names appear in tagged faces list
- ✅ Confidence shows 100% (manual tag)
- ✅ Tagged by current user
- ✅ Timestamp shown

**Pass Criteria**: Both faces successfully tagged and visible

---

### Test 1.3: Delete Face Tag
**User**: Editor or Admin  
**Objective**: Remove a face tag

**Steps**:
1. Complete Test 1.2 (tagged faces)
2. Click trash icon next to "Bob Johnson"
3. Confirm deletion
4. Verify tag removed

**Expected Results**:
- ✅ Confirmation dialog appears
- ✅ Success message: "Face tag deleted"
- ✅ Tagged faces count decreases to 1
- ✅ Only "Alice Smith" remains in list

**Pass Criteria**: Tag successfully deleted

---

### Test 1.4: Permission Check
**User**: Editor (non-owner)  
**Objective**: Verify RBAC protection

**Steps**:
1. Login as Editor A
2. Upload photo with faces
3. Tag a face as "Test User"
4. Logout, login as Editor B
5. Try to access Editor A's photo
6. Attempt to detect/tag faces

**Expected Results**:
- ✅ Editor B cannot see Editor A's photo in gallery
- ✅ Direct URL access returns 403 Forbidden
- ✅ Face tagging not accessible

**Pass Criteria**: Proper permission enforcement

---

## Test Scenario 2: Auto Face Recognition

### Test 2.1: First Photo Upload
**User**: Editor or Admin  
**Objective**: Establish baseline face data

**Steps**:
1. Login as editor/admin
2. Upload photo A with person "Charlie"
3. Wait for upload to complete
4. Manually tag Charlie using Test 1.2 steps
5. Verify tag stored in database

**Expected Results**:
- ✅ Photo uploaded successfully
- ✅ Face detected automatically (check logs)
- ✅ Manual tag created with 100% confidence
- ✅ Face embedding stored in database

**Pass Criteria**: Baseline face data established

---

### Test 2.2: Auto-Recognition on Upload
**User**: Same editor/admin from Test 2.1  
**Objective**: Verify auto-recognition works

**Steps**:
1. Upload photo B with same person "Charlie"
2. Wait for upload to complete
3. Check photo detail page immediately
4. Look for auto-tagged faces
5. Verify confidence score < 100%

**Expected Results**:
- ✅ Upload progress shows "Recognizing faces..."
- ✅ Charlie auto-tagged in photo B
- ✅ Confidence: 60-95% (not 100%)
- ✅ Tagged faces list shows auto-tag badge
- ✅ Auto-tag created by system/uploader

**Pass Criteria**: Charlie automatically recognized

---

### Test 2.3: Multiple Faces Auto-Recognition
**User**: Editor or Admin  
**Objective**: Test recognition with multiple people

**Steps**:
1. Upload photo C with "Alice" and "Charlie" (both previously tagged)
2. Upload photo D with "Alice", "Bob" (new), and "Charlie"
3. Check auto-recognition results

**Expected Results**:
Photo C:
- ✅ Alice and Charlie both auto-recognized
- ✅ 2 faces auto-tagged

Photo D:
- ✅ Alice and Charlie auto-recognized
- ✅ Bob not recognized (new face)
- ✅ 2 auto-tags, 1 detected but untagged

**Pass Criteria**: Correct recognition of known faces

---

### Test 2.4: False Positive Check
**User**: Editor or Admin  
**Objective**: Verify no incorrect matches

**Steps**:
1. Upload photo E with 3 completely new people
2. Check for auto-tags
3. Verify no false matches

**Expected Results**:
- ✅ 3 faces detected
- ✅ 0 faces auto-tagged
- ✅ No incorrect name assignments
- ✅ All faces available for manual tagging

**Pass Criteria**: No false positive recognitions

---

## Test Scenario 3: Face Capture at Login

### Test 3.1: First-Time Viewer Login
**User**: New viewer account  
**Objective**: Verify face capture modal appears

**Steps**:
1. Create new viewer user (or use fresh account)
2. Login to application
3. Verify camera modal appears automatically
4. Check modal content

**Expected Results**:
- ✅ Modal appears after login (not closeable by clicking outside)
- ✅ Title: "📸 Capture Your Face"
- ✅ Instructions shown
- ✅ Camera preview displays (after permission granted)
- ✅ "Take Photo" and "Skip for Now" buttons visible

**Pass Criteria**: Modal appears for new viewer

---

### Test 3.2: Camera Permission Grant
**User**: Viewer  
**Objective**: Grant camera access

**Steps**:
1. Continue from Test 3.1
2. Grant camera permission when prompted
3. Verify camera feed displays

**Expected Results**:
- ✅ Browser asks for camera permission
- ✅ After granting, live video feed appears
- ✅ Feed shows current user's face
- ✅ No error messages

**Pass Criteria**: Camera access working

---

### Test 3.3: Face Capture Process
**User**: Viewer  
**Objective**: Complete face capture

**Steps**:
1. Continue from Test 3.2
2. Position face in frame (good lighting)
3. Click "Take Photo" button
4. Verify captured image preview
5. Click "Confirm & Save"
6. Wait for processing

**Expected Results**:
- ✅ Captured image freezes and displays
- ✅ "Retake" button appears
- ✅ "Confirm & Save" button appears
- ✅ Processing shows spinner
- ✅ Success message: "Face captured successfully"
- ✅ Modal closes after 2 seconds

**Pass Criteria**: Face successfully captured and stored

---

### Test 3.4: Face Capture Validation
**User**: Viewer  
**Objective**: Test validation rules

**Steps**:
1. Login as new viewer
2. When modal appears, capture photo with:
   - Test A: No face in frame
   - Test B: Multiple people in frame
   - Test C: Valid single face

**Expected Results**:
Test A (no face):
- ❌ Error: "No face detected. Please try again..."

Test B (multiple faces):
- ❌ Error: "Multiple faces detected. Please ensure only your face is visible."

Test C (single face):
- ✅ Success: "Face captured successfully"

**Pass Criteria**: Validation working correctly

---

### Test 3.5: Skip Face Capture
**User**: Viewer  
**Objective**: Test skip functionality

**Steps**:
1. Login as new viewer
2. Click "Skip for Now"
3. Verify modal closes
4. Logout and login again
5. Check if modal reappears

**Expected Results**:
- ✅ Modal closes immediately
- ✅ Application accessible without face
- ✅ Modal reappears on next login (no profile saved)

**Pass Criteria**: Skip works, profile not saved

---

### Test 3.6: Existing Profile Check
**User**: Viewer with existing face profile  
**Objective**: Verify modal doesn't show for existing profiles

**Steps**:
1. Complete Test 3.3 (save face profile)
2. Logout
3. Login again
4. Check if modal appears

**Expected Results**:
- ✅ Modal does NOT appear
- ✅ User goes directly to dashboard
- ✅ No camera access requested

**Pass Criteria**: Modal skipped for existing profiles

---

## Test Scenario 4: Face-Based Photo Filtering

### Test 4.1: Admin User - No Filtering
**User**: Admin  
**Objective**: Verify admins see all photos

**Steps**:
1. Login as admin
2. Navigate to photo gallery
3. Check visible photos
4. Count total photos

**Expected Results**:
- ✅ All photos visible (regardless of faces)
- ✅ Photos from all users shown
- ✅ No face-based filtering applied

**Pass Criteria**: Admin sees everything

---

### Test 4.2: Editor User - Ownership Filtering
**User**: Editor  
**Objective**: Verify editors see only their photos

**Steps**:
1. Login as Editor A
2. Upload 3 photos (with and without faces)
3. Note photo count
4. Logout, login as Editor B
5. Check photo gallery

**Expected Results**:
Editor A:
- ✅ Sees own 3 photos

Editor B:
- ✅ Does NOT see Editor A's photos
- ✅ Only sees own uploaded photos

**Pass Criteria**: Ownership-based filtering works

---

### Test 4.3: Viewer User - Face Filtering (No Profile)
**User**: Viewer without face profile  
**Objective**: Verify behavior without face profile

**Steps**:
1. Login as viewer (skipped face capture)
2. Check photo gallery
3. Note visible photos

**Expected Results**:
- ✅ No photos shown OR all photos shown (depending on implementation)
- ✅ Message suggesting to set up face profile
- ✅ Link to capture face

**Pass Criteria**: Appropriate behavior for no profile

---

### Test 4.4: Viewer User - Face Filtering (With Profile)
**User**: Viewer with face profile  
**Objective**: Verify face-based filtering works

**Setup**:
1. Admin uploads 5 photos:
   - Photo 1: Contains Viewer A's face
   - Photo 2: Contains Viewer B's face
   - Photo 3: Contains both Viewer A and B
   - Photo 4: Contains unknown person
   - Photo 5: No faces (landscape)
2. Viewer A has face profile set up

**Steps**:
1. Login as Viewer A
2. Navigate to photo gallery
3. Count visible photos
4. Verify which photos appear

**Expected Results**:
- ✅ Photo 1 visible (contains Viewer A)
- ✅ Photo 3 visible (contains Viewer A)
- ❌ Photo 2 NOT visible (only Viewer B)
- ❌ Photo 4 NOT visible (unknown person)
- ❌ Photo 5 NOT visible (no faces)
- ✅ Total: 2 photos visible

**Pass Criteria**: Only photos with Viewer A's face shown

---

### Test 4.5: Search with Face Filtering
**User**: Viewer with face profile  
**Objective**: Verify search respects face filtering

**Setup**: Use same 5 photos from Test 4.4

**Steps**:
1. Login as Viewer A
2. Search for "beach" (assume Photos 1, 2, 5 have beach tag)
3. Check search results

**Expected Results**:
- ✅ Photo 1 in results (beach + Viewer A's face)
- ❌ Photo 2 NOT in results (beach but no Viewer A)
- ❌ Photo 5 NOT in results (beach but no faces)
- ✅ Only 1 result returned

**Pass Criteria**: Search filtered by face

---

## Test Scenario 5: Cross-User Recognition

### Test 5.1: Cross-User Face Recognition
**User**: Multiple users  
**Objective**: Verify face recognition works across users

**Steps**:
1. Editor A uploads photo with "David", tags him
2. Editor B uploads different photo with same "David"
3. Check if David auto-recognized in Editor B's photo

**Expected Results**:
- ✅ David auto-tagged in Editor B's photo
- ✅ Uses Editor A's embedding for matching
- ✅ Both editors can see their respective photos
- ✅ Cross-user recognition enabled

**Pass Criteria**: Recognition works across users

---

### Test 5.2: Viewer Sees Cross-User Photos
**User**: Viewer  
**Objective**: Verify viewer sees photos from all users if their face is tagged

**Steps**:
1. Editor A uploads photo with Viewer C's face, tags "Viewer C"
2. Editor B uploads photo with Viewer C's face, tags "Viewer C"
3. Admin uploads photo with Viewer C's face, tags "Viewer C"
4. Login as Viewer C
5. Check photo gallery

**Expected Results**:
- ✅ Viewer C sees all 3 photos
- ✅ Photos from different uploaders shown
- ✅ Only photos with Viewer C's face visible

**Pass Criteria**: Cross-user photo visibility works

---

## Test Scenario 6: Performance Testing

### Test 6.1: Face Detection Speed
**Objective**: Measure face detection performance

**Steps**:
1. Upload photo with 1 face
2. Click "Detect Faces"
3. Measure time to completion
4. Repeat with photos of 2, 3, 5 faces

**Expected Results**:
- 1 face: < 2 seconds
- 2 faces: < 3 seconds
- 3-5 faces: < 5 seconds

**Pass Criteria**: Detection within acceptable time

---

### Test 6.2: Auto-Recognition with Large Dataset
**Objective**: Test recognition performance with many known faces

**Steps**:
1. Pre-populate database with 100 tagged faces
2. Upload new photo with 1 known face
3. Measure auto-recognition time
4. Check accuracy

**Expected Results**:
- Recognition time: < 3 seconds
- Correct match found
- No performance degradation

**Pass Criteria**: Scales to 100+ known faces

---

### Test 6.3: Concurrent Face Detection
**Objective**: Test multiple simultaneous face operations

**Steps**:
1. Login with 3 different users (different browsers)
2. All users upload photos with faces simultaneously
3. All click "Detect Faces" at same time
4. Verify all complete successfully

**Expected Results**:
- ✅ All detections complete
- ✅ No database locks or errors
- ✅ Results isolated per user

**Pass Criteria**: Handles concurrent operations

---

## Test Scenario 7: Error Handling

### Test 7.1: No Faces in Photo
**User**: Editor  
**Objective**: Handle photos without faces gracefully

**Steps**:
1. Upload landscape photo (no people)
2. Click "Detect Faces"
3. Check response

**Expected Results**:
- ✅ Message: "Detected 0 face(s)"
- ✅ No error thrown
- ✅ Can still view/manage photo

**Pass Criteria**: Handles zero faces gracefully

---

### Test 7.2: Camera Not Available
**User**: Viewer on device without camera  
**Objective**: Handle missing camera

**Steps**:
1. Login as viewer on device without camera
2. Check face capture modal

**Expected Results**:
- ✅ Error message: "Unable to access camera..."
- ✅ "Skip for Now" button still works
- ✅ No application crash

**Pass Criteria**: Graceful degradation

---

### Test 7.3: Duplicate Face Tag
**User**: Editor  
**Objective**: Test duplicate tagging

**Steps**:
1. Detect faces in photo
2. Tag Face 1 as "Alice"
3. Detect faces again
4. Try to tag same Face 1 as "Alice" again

**Expected Results**:
- ✅ Either: Allows duplicate (separate records)
- ✅ Or: Shows warning about existing tag
- ✅ No database constraint error

**Pass Criteria**: Handles duplicates without crash

---

### Test 7.4: Database Connection Loss
**User**: Any  
**Objective**: Handle DB failures gracefully

**Steps**:
1. Simulate DB connection loss (stop Oracle)
2. Try to detect faces
3. Try to tag face
4. Check error handling

**Expected Results**:
- ❌ Clear error message shown
- ✅ No stack traces exposed to user
- ✅ Application remains responsive
- ✅ Can retry when DB restored

**Pass Criteria**: Proper error handling

---

## Test Scenario 8: Integration Testing

### Test 8.1: Complete Upload-to-Search Flow
**User**: Editor + Viewer  
**Objective**: Test full workflow

**Steps**:
1. Editor uploads photo with Viewer's face
2. Editor tags Viewer's name
3. Viewer logs in (face capture if needed)
4. Viewer searches for keywords in photo
5. Verify photo appears in Viewer's results

**Expected Results**:
- ✅ Upload successful
- ✅ Face tagged
- ✅ Auto-recognition works on subsequent uploads
- ✅ Viewer sees photo in search
- ✅ Face filtering applied correctly

**Pass Criteria**: End-to-end flow works

---

### Test 8.2: Multi-Album Face Tagging
**User**: Editor  
**Objective**: Test across multiple albums

**Steps**:
1. Create 3 albums: "Vacation", "Office", "Family"
2. Upload photos with same person to all 3 albums
3. Tag person in "Vacation" album
4. Upload new photos to "Office" and "Family"
5. Check auto-recognition

**Expected Results**:
- ✅ Auto-recognized in all albums
- ✅ Face data shared across albums
- ✅ Search within album respects filtering

**Pass Criteria**: Works across albums

---

## Test Results Summary

| Test Scenario | Test Cases | Expected Pass | Actual Pass | Status |
|--------------|------------|---------------|-------------|--------|
| 1. Manual Tagging | 4 | 4 | - | ⏳ Pending |
| 2. Auto Recognition | 4 | 4 | - | ⏳ Pending |
| 3. Face Capture | 6 | 6 | - | ⏳ Pending |
| 4. Face Filtering | 5 | 5 | - | ⏳ Pending |
| 5. Cross-User | 2 | 2 | - | ⏳ Pending |
| 6. Performance | 3 | 3 | - | ⏳ Pending |
| 7. Error Handling | 4 | 4 | - | ⏳ Pending |
| 8. Integration | 2 | 2 | - | ⏳ Pending |
| **Total** | **30** | **30** | **-** | **⏳ Pending** |

---

## Bug Tracking Template

### Bug Report Format
```
Bug ID: FT-XXX
Title: [Brief description]
Severity: Critical / High / Medium / Low
Steps to Reproduce:
1. 
2. 
3. 

Expected Result:
Actual Result:
Screenshots/Logs:
Environment: Production VM / Local Dev
Assigned To:
Status: Open / In Progress / Fixed / Verified
```

---

## Performance Benchmarks

### Target Metrics
- Face Detection: < 2s per photo
- Auto Recognition: < 3s with 100 known faces
- Face Capture: < 1s processing
- Search with Face Filter: < 500ms
- Concurrent Users: Support 10+ simultaneous operations

### Actual Metrics (To be filled during testing)
- Face Detection: ___ seconds
- Auto Recognition: ___ seconds
- Face Capture: ___ seconds
- Search with Filter: ___ ms
- Max Concurrent Users Tested: ___

---

## Sign-Off

### Testing Completed By
- **Tester Name**: _______________
- **Date**: _______________
- **Total Tests Passed**: ___ / 30
- **Critical Bugs Found**: ___
- **Recommendation**: ☐ Approve for Production ☐ Needs Fixes

### Deployment Approval
- **Approved By**: _______________
- **Date**: _______________
- **Notes**: _______________

---

**Document Version**: 1.0  
**Last Updated**: December 19, 2024  
**Next Review**: After deployment to production
