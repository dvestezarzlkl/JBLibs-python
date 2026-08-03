# JBLibs mail transport

`mail.py` provides a reusable SMTP transport without any dependency on the
Terminal Manager application configuration.

## SMTP settings

```python
from libs.JBLibs.mail import SmtpSettings

smtp = SmtpSettings(
    host="smtp.example.com",
    port=465,
    mode="ssl",          # plain / starttls / ssl
    username="service@example.com",
    password="secret",
    timeout=20,
)
```

`username` and `password` are optional for a trusted local relay, but they must
be configured together. The password is never included in errors or message
objects.

## Attachments

Attachments may be backed by a filesystem path, bytes, or an already opened
stream:

```python
from io import BytesIO
from libs.JBLibs.mail import MailAttachment

attachments = [
    MailAttachment.from_path("/tmp/report.pdf"),
    MailAttachment.from_bytes("info.txt", b"text"),
    MailAttachment.from_stream("data.bin", BytesIO(b"payload")),
]
```

Streams are read from their current position and are not closed by the helper.
The caller remains responsible for their lifetime.

## ZIP without temporary files

```python
from libs.JBLibs.mail import ZipItem, create_zip_attachment

archive = create_zip_attachment(
    "ssh-keys.zip",
    [
        ZipItem("private.key", private_key_bytes),
        ZipItem("public.key", public_key_bytes),
    ],
)
```

The returned value is a regular `MailAttachment` with MIME type
`application/zip`. ZIP item names must be unique and are reduced to safe base
filenames.

## Build and send

`build_message()` creates and validates an `EmailMessage` without opening a
network connection. This is useful for tests and previews.

```python
from libs.JBLibs.mail import build_message, send_message

message, envelope = build_message(
    mail_from="service@example.com",
    recipients=["user@example.com"],
    subject="Instance handover protocol",
    body="See attached protocol.",
    attachments=[archive],
)

ok, error = send_message(
    smtp_settings=smtp,
    mail_from="service@example.com",
    recipients=["user@example.com"],
    subject="Instance handover protocol",
    body="See attached protocol.",
    attachments=[archive],
)
```

BCC recipients are included only in the SMTP envelope and never written into a
message header. Invalid recipient entries are ignored, but at least one valid
`To` address is required.
