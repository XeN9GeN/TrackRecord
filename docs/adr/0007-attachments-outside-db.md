# ADR-0007: Attachments are stored outside the database

**Status:** accepted

## Context
Log entries carry photos, scans, audio and video from machines. Rough estimate: around 100 GB
per year. Storing files in PostgreSQL (`bytea`, large objects) or MongoDB GridFS would bloat the
database and its backups, push every upload through WAL, and make video streaming go through
the application.

## Decision
- The database stores only metadata in `Attachment`: log entry, storage key, original name,
  content type, size, SHA-256, kind (photo, scan, video, audio, document), thumbnail,
  uploader, upload time.
- Files are written through the Django Storage API only, never with direct filesystem calls.
  Key layout: `attachments/YYYY/MM/<uuid>.<ext>`. The original name is used only in
  `Content-Disposition`. Stored files are immutable.
- MVP storage: a local volume (`MEDIA_ROOT`). Later: an S3-compatible object store through
  `django-storages` (corporate S3, SeaweedFS or Ceph; MinIO only after checking its current
  licence and distribution terms). Switching is a settings change.
- Files are never served as a public directory. A Django view checks that the user is signed in
  and returns `X-Accel-Redirect`; nginx sends the file (supports HTTP range for video).
  With S3, short-lived presigned URLs are used instead.
- Upload checks: size limit in Django and nginx (`client_max_body_size`), content type detected
  from file content (`python-magic`), responses with `X-Content-Type-Options: nosniff`.
- Processing: photo thumbnails with Pillow (+ `pillow-heif` for iPhone HEIC) in the MVP.
  Video transcoding to browser-friendly MP4 (ffmpeg) and PDF previews (poppler) later, in the
  background; the original is always kept.
- Backups: nightly `pg_dump` plus incremental backup of the storage (restic/rsync).
  A `check_attachments` command reconciles database rows and stored files by SHA-256.

## Consequences
- The database stays small and fast to back up and restore.
- Storage size must be planned separately with IT (dedicated disk or bucket).
- A file and its database row are not in one transaction: the row is created only after the file
  is stored, and orphaned files are found by `check_attachments`.
