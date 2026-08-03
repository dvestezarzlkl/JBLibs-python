from __future__ import annotations

import io
import mimetypes
import re
import smtplib
import zipfile
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import BinaryIO, Iterable, Optional, Sequence, Tuple, Union


_SMTP_MODES = {"plain", "starttls", "ssl"}
_MAIL_RGX = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

AttachmentSource = Union[str, Path, bytes, bytearray, memoryview, BinaryIO]


@dataclass(frozen=True)
class SmtpSettings:
    """Explicit SMTP connection settings used by :func:`send_message`."""

    host: str
    port: int
    mode: str = "starttls"
    username: str = ""
    password: str = ""
    timeout: int = 20

    def validate(self) -> Tuple[bool, Optional[str]]:
        host = self.host.strip() if isinstance(self.host, str) else ""
        if not host:
            return False, "SMTP host is not configured."

        try:
            port = int(self.port)
        except (TypeError, ValueError):
            return False, "SMTP port is invalid."
        if port <= 0 or port > 65535:
            return False, "SMTP port is invalid."

        mode = self.mode.strip().lower() if isinstance(self.mode, str) else ""
        if mode not in _SMTP_MODES:
            return False, "SMTP mode must be plain, starttls, or ssl."

        try:
            timeout = int(self.timeout)
        except (TypeError, ValueError):
            return False, "SMTP timeout is invalid."
        if timeout <= 0:
            return False, "SMTP timeout is invalid."

        username = self.username if isinstance(self.username, str) else ""
        password = self.password if isinstance(self.password, str) else ""
        if bool(username) != bool(password):
            return False, "SMTP username and password must be configured together."

        return True, None


@dataclass(frozen=True)
class MailAttachment:
    """One MIME attachment backed by a path, bytes, or an open stream."""

    filename: str
    source: AttachmentSource
    content_type: Optional[str] = None

    @classmethod
    def from_path(
        cls,
        path: Union[str, Path],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> "MailAttachment":
        source = Path(path)
        return cls(filename or source.name, source, content_type)

    @classmethod
    def from_bytes(
        cls,
        filename: str,
        data: Union[bytes, bytearray, memoryview],
        content_type: Optional[str] = None,
    ) -> "MailAttachment":
        return cls(filename, data, content_type)

    @classmethod
    def from_stream(
        cls,
        filename: str,
        stream: BinaryIO,
        content_type: Optional[str] = None,
    ) -> "MailAttachment":
        return cls(filename, stream, content_type)

    def safe_filename(self) -> str:
        if not isinstance(self.filename, str):
            raise ValueError("Attachment filename must be a string.")
        filename = Path(self.filename.strip()).name
        if not filename or "\x00" in filename or "\n" in filename or "\r" in filename:
            raise ValueError("Attachment filename is invalid.")
        return filename

    def read_bytes(self) -> bytes:
        source = self.source
        if isinstance(source, Path):
            return source.read_bytes()
        if isinstance(source, str):
            return Path(source).read_bytes()
        if isinstance(source, bytes):
            return source
        if isinstance(source, (bytearray, memoryview)):
            return bytes(source)
        if hasattr(source, "read"):
            data = source.read()
            if isinstance(data, str):
                return data.encode("utf-8")
            if isinstance(data, (bytes, bytearray, memoryview)):
                return bytes(data)
            raise TypeError("Attachment stream must return bytes or text.")
        raise TypeError("Unsupported attachment source.")

    def mime_type(self) -> Tuple[str, str]:
        content_type = self.content_type
        if not content_type:
            content_type, _ = mimetypes.guess_type(self.safe_filename())
        if not content_type or "/" not in content_type:
            content_type = "application/octet-stream"
        maintype, subtype = content_type.split("/", 1)
        return maintype, subtype


@dataclass(frozen=True)
class ZipItem:
    """One file stored inside an in-memory ZIP attachment."""

    filename: str
    source: AttachmentSource

    def as_attachment(self) -> MailAttachment:
        return MailAttachment(self.filename, self.source)


def is_valid_mail_address(mail: str) -> bool:
    if not isinstance(mail, str):
        return False
    return bool(_MAIL_RGX.match(mail.strip()))


def unique_addresses(addresses: Iterable[str]) -> list[str]:
    unique: list[str] = []
    for address in addresses:
        if not isinstance(address, str):
            continue
        address = address.strip().lower()
        if not address or not is_valid_mail_address(address):
            continue
        if address not in unique:
            unique.append(address)
    return unique


def create_zip_attachment(
    filename: str,
    items: Sequence[ZipItem],
    compression: int = zipfile.ZIP_DEFLATED,
) -> MailAttachment:
    """Create an in-memory ZIP attachment without temporary files."""

    zip_name = MailAttachment(filename, b"").safe_filename()
    buffer = io.BytesIO()
    used_names: set[str] = set()

    with zipfile.ZipFile(buffer, mode="w", compression=compression) as archive:
        for item in items:
            attachment = item.as_attachment()
            item_name = attachment.safe_filename()
            if item_name in used_names:
                raise ValueError(f"Duplicate ZIP item filename: {item_name}")
            used_names.add(item_name)
            archive.writestr(item_name, attachment.read_bytes())

    return MailAttachment.from_bytes(zip_name, buffer.getvalue(), "application/zip")


def build_message(
    mail_from: str,
    recipients: Sequence[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    cc: Optional[Sequence[str]] = None,
    bcc: Optional[Sequence[str]] = None,
    reply_to: Optional[str] = None,
    attachments: Optional[Sequence[MailAttachment]] = None,
) -> Tuple[EmailMessage, list[str]]:
    """Build an :class:`EmailMessage` and its SMTP envelope recipients."""

    if not is_valid_mail_address(mail_from):
        raise ValueError("Mail from address is invalid.")

    to_list = unique_addresses(recipients)
    cc_list = unique_addresses(cc or [])
    bcc_list = unique_addresses(bcc or [])
    envelope_recipients = unique_addresses([*to_list, *cc_list, *bcc_list])
    if not envelope_recipients:
        raise ValueError("No valid mail recipients configured.")
    if not to_list:
        raise ValueError("At least one valid To recipient is required.")

    msg = EmailMessage()
    msg["From"] = mail_from.strip().lower()
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if reply_to:
        if not is_valid_mail_address(reply_to):
            raise ValueError("Reply-To address is invalid.")
        msg["Reply-To"] = reply_to.strip().lower()
    msg["Subject"] = str(subject)
    msg.set_content(str(body))

    if html_body is not None:
        msg.add_alternative(str(html_body), subtype="html")

    for attachment in attachments or []:
        if not isinstance(attachment, MailAttachment):
            raise TypeError("Attachments must contain MailAttachment instances.")
        maintype, subtype = attachment.mime_type()
        msg.add_attachment(
            attachment.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment.safe_filename(),
        )

    return msg, envelope_recipients


def send_message(
    smtp_settings: SmtpSettings,
    mail_from: str,
    recipients: Sequence[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    cc: Optional[Sequence[str]] = None,
    bcc: Optional[Sequence[str]] = None,
    reply_to: Optional[str] = None,
    attachments: Optional[Sequence[MailAttachment]] = None,
) -> Tuple[bool, Optional[str]]:
    """Send a message using explicit SMTP settings.

    Returns ``(True, None)`` on success and never logs or exposes the password.
    """

    ok, error = smtp_settings.validate()
    if not ok:
        return False, error

    try:
        message, envelope_recipients = build_message(
            mail_from=mail_from,
            recipients=recipients,
            subject=subject,
            body=body,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            attachments=attachments,
        )
    except Exception as exc:
        return False, str(exc)

    host = smtp_settings.host.strip()
    port = int(smtp_settings.port)
    mode = smtp_settings.mode.strip().lower()
    timeout = int(smtp_settings.timeout)

    try:
        if mode == "ssl":
            smtp = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            smtp = smtplib.SMTP(host, port, timeout=timeout)

        with smtp:
            smtp.ehlo()
            if mode == "starttls":
                smtp.starttls()
                smtp.ehlo()
            if smtp_settings.username:
                smtp.login(smtp_settings.username, smtp_settings.password)
            smtp.send_message(
                message,
                from_addr=mail_from.strip().lower(),
                to_addrs=envelope_recipients,
            )
    except Exception as exc:
        return False, f"Failed to send mail via SMTP: {exc}"

    return True, None
