import os
import logging

logger = logging.getLogger('oci_config')

def resolve_repo_local_config():
    # Compute project-relative path to the repo-local .oci/config
    base = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(base, '..'))
    return os.path.join(repo_root, '.oci', 'config')


def load_oci_config(oci_module):
    """Return an OCI config dict using precedence:
    1) OCI_CONFIG_PATH env var (if set and exists)
    2) repository-local .oci/config
    3) default oci.config.from_file() behavior

    `oci_module` should be the imported oci package.
    """
    if not oci_module:
        raise RuntimeError('OCI module not available')

    env_path = os.getenv('OCI_CONFIG_PATH')
    if env_path and os.path.exists(env_path):
        logger.info('Using OCI config from OCI_CONFIG_PATH: %s', env_path)
        return oci_module.config.from_file(file_location=env_path)

    repo_cfg = resolve_repo_local_config()
    if os.path.exists(repo_cfg):
        logger.info('Using repository-local OCI config: %s', repo_cfg)
        return oci_module.config.from_file(file_location=repo_cfg)

    logger.info('Falling back to default OCI config lookup')
    return oci_module.config.from_file()
