import oci, time

def gen_pars(paths):
    try:
        cfg = oci.config.from_file('twelvelabvideoai/.oci/config')
        client = oci.object_storage.ObjectStorageClient(cfg)
        out = {}
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
                out[p] = None
                continue
            expiry = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int(time.time()) + 3600))
            details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
                name='batch-par', object_name=obj,
                access_type=oci.object_storage.models.CreatePreauthenticatedRequestDetails.ACCESS_TYPE_OBJECT_READ,
                time_expires=expiry)
            par = client.create_preauthenticated_request(namespace, bucket, details)
            access_uri = getattr(par.data, 'access_uri', None) or getattr(par.data, 'accessUri', None)
            base = client.base_client.endpoint
            out[p] = base.rstrip('/') + access_uri if access_uri else None
        return out
    except Exception as e:
        print('ERROR', e)
        return {}

if __name__ == '__main__':
    base = 'oci://apaccpt01/Media/photos/isha/'
    # generate DSC00769..DSC00782 (14 files)
    paths = [base + f'DSC{str(i).zfill(5)}.JPG' for i in range(769, 783)]
    res = gen_pars(paths)
    for k, v in res.items():
        print(k, '->', v)
