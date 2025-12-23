-- Add flag to track ImageBind processed embeddings
-- Run this to enable tracking of which faces have been processed

alter table face_tags add (
   imagebind_processed number(1) default 0
);

-- Create index for faster queries
create index idx_imagebind_processed on
   face_tags (
      imagebind_processed
   );

-- Mark all existing faces as needing processing
update face_tags
   set
   imagebind_processed = 0;

commit;