import oci, time

config_file = 'twelvelabvideoai/.oci/config'
paths = ['oci://apaccpt01/Media/photos/isha/DSC00769.JPG']

try:
    cfg = oci.config.from_file(config_file)
    client = oci.object_storage.ObjectStorageClient(cfg)
    for p in paths:
        path = p[len('oci://'):]
        parts = path.split('/', 2)
        if len(parts) == 2:
            namespace = client.get_namespace().data
            bucket = parts[0]
            obj = parts[1]
        elif len(parts) == 3:
            namespace = parts[0]
            bucket = parts[1]
            obj = parts[2]
        else:
            print('invalid path', p)
            continue
        expiry = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int(time.time()) + 3600))
        details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name='debug-par', object_name=obj,
            access_type=oci.object_storage.models.CreatePreauthenticatedRequestDetails.ACCESS_TYPE_OBJECT_READ,
            time_expires=expiry)
        par = client.create_preauthenticated_request(namespace, bucket, details)
        access_uri = getattr(par.data, 'access_uri', None) or getattr(par.data, 'accessUri', None)
        base = client.base_client.endpoint
        if access_uri:
            print(p, '->', base.rstrip('/') + access_uri)
        else:
            print('no access_uri for', p)
except Exception as e:
    print('ERROR', e)
