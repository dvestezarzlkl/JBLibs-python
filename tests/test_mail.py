import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import mail


class FakeSMTP:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        self.calls.append(("ehlo",))

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message, from_addr, to_addrs):
        self.calls.append(("send_message", message, from_addr, to_addrs))


class FailingSMTP(FakeSMTP):
    def login(self, username, password):
        raise RuntimeError(f"authentication failed for password {password}")


class MailTests(unittest.TestCase):
    def test_smtp_settings_validation_and_hidden_password_repr(self):
        self.assertEqual(mail.SmtpSettings("", 25).validate()[0], False)
        self.assertEqual(mail.SmtpSettings("smtp.example.test", 0).validate()[0], False)
        self.assertEqual(
            mail.SmtpSettings("smtp.example.test", 25, mode="invalid").validate()[0],
            False,
        )
        self.assertEqual(
            mail.SmtpSettings("smtp.example.test", 25, username="user").validate()[0],
            False,
        )
        settings = mail.SmtpSettings(
            "smtp.example.test",
            25,
            mode="plain",
            username="user",
            password="secret-value",
        )
        self.assertEqual(settings.validate(), (True, None))
        self.assertNotIn("secret-value", repr(settings))

    def test_build_message_with_bytes_attachment_and_bcc_envelope(self):
        attachment = mail.MailAttachment.from_bytes(
            "report.txt",
            b"hello",
            "text/plain",
        )
        message, envelope = mail.build_message(
            mail_from="sender@example.test",
            recipients=["User@example.test", "user@example.test", "invalid"],
            cc=["copy@example.test"],
            bcc=["hidden@example.test"],
            subject="Subject",
            body="Body",
            attachments=[attachment],
        )

        self.assertEqual(message["To"], "user@example.test")
        self.assertEqual(message["Cc"], "copy@example.test")
        self.assertIsNone(message["Bcc"])
        self.assertEqual(
            envelope,
            ["user@example.test", "copy@example.test", "hidden@example.test"],
        )

        attachments = list(message.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), "report.txt")
        self.assertEqual(attachments[0].get_content_type(), "text/plain")
        self.assertEqual(attachments[0].get_payload(decode=True), b"hello")

    def test_build_message_adds_required_date_header(self):
        expected = "Tue, 04 Aug 2026 09:40:00 +0200"
        with patch("mail.formatdate", return_value=expected):
            message, _ = mail.build_message(
                mail_from="sender@example.test",
                recipients=["user@example.test"],
                subject="Subject",
                body="Body",
            )

        self.assertEqual(message["Date"], expected)

    def test_path_and_stream_attachments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "path.bin"
            path.write_bytes(b"path-data")
            stream = io.BytesIO(b"stream-data")

            message, _ = mail.build_message(
                mail_from="sender@example.test",
                recipients=["user@example.test"],
                subject="Subject",
                body="Body",
                attachments=[
                    mail.MailAttachment.from_path(path),
                    mail.MailAttachment.from_stream("stream.bin", stream),
                ],
            )

        payloads = {
            part.get_filename(): part.get_payload(decode=True)
            for part in message.iter_attachments()
        }
        self.assertEqual(payloads["path.bin"], b"path-data")
        self.assertEqual(payloads["stream.bin"], b"stream-data")

    def test_create_zip_attachment_without_temp_file(self):
        attachment = mail.create_zip_attachment(
            "keys.zip",
            [
                mail.ZipItem("private.key", b"private"),
                mail.ZipItem("public.key", io.BytesIO(b"public")),
            ],
        )

        self.assertEqual(attachment.safe_filename(), "keys.zip")
        self.assertEqual(attachment.mime_type(), ("application", "zip"))
        with zipfile.ZipFile(io.BytesIO(attachment.read_bytes()), "r") as archive:
            self.assertEqual(archive.namelist(), ["private.key", "public.key"])
            self.assertEqual(archive.read("private.key"), b"private")
            self.assertEqual(archive.read("public.key"), b"public")

    def test_zip_rejects_duplicate_names(self):
        with self.assertRaises(ValueError):
            mail.create_zip_attachment(
                "duplicate.zip",
                [mail.ZipItem("same.txt", b"a"), mail.ZipItem("same.txt", b"b")],
            )

    def test_send_message_starttls(self):
        fake = FakeSMTP("smtp.example.test", 587, 10)
        with patch("mail.smtplib.SMTP", return_value=fake):
            ok, error = mail.send_message(
                smtp_settings=mail.SmtpSettings(
                    "smtp.example.test",
                    587,
                    mode="starttls",
                    username="user",
                    password="secret",
                    timeout=10,
                ),
                mail_from="sender@example.test",
                recipients=["recipient@example.test"],
                subject="Subject",
                body="Body",
            )

        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertEqual(fake.calls[0], ("ehlo",))
        self.assertEqual(fake.calls[1], ("starttls",))
        self.assertEqual(fake.calls[2], ("ehlo",))
        self.assertEqual(fake.calls[3], ("login", "user", "secret"))
        self.assertEqual(fake.calls[4][0], "send_message")
        self.assertEqual(fake.calls[4][2], "sender@example.test")
        self.assertEqual(fake.calls[4][3], ["recipient@example.test"])

    def test_send_message_ssl_without_auth(self):
        fake = FakeSMTP("smtp.example.test", 465, 20)
        with patch("mail.smtplib.SMTP_SSL", return_value=fake):
            ok, error = mail.send_message(
                smtp_settings=mail.SmtpSettings(
                    "smtp.example.test",
                    465,
                    mode="ssl",
                ),
                mail_from="sender@example.test",
                recipients=["recipient@example.test"],
                subject="Subject",
                body="Body",
            )

        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertFalse(any(call[0] == "starttls" for call in fake.calls))
        self.assertFalse(any(call[0] == "login" for call in fake.calls))

    def test_send_message_redacts_password_from_error(self):
        password = "top-secret-password"
        fake = FailingSMTP("smtp.example.test", 587, 20)
        with patch("mail.smtplib.SMTP", return_value=fake):
            ok, error = mail.send_message(
                smtp_settings=mail.SmtpSettings(
                    "smtp.example.test",
                    587,
                    mode="starttls",
                    username="user",
                    password=password,
                ),
                mail_from="sender@example.test",
                recipients=["recipient@example.test"],
                subject="Subject",
                body="Body",
            )

        self.assertFalse(ok)
        self.assertIsNotNone(error)
        self.assertNotIn(password, error)
        self.assertIn("***", error)


if __name__ == "__main__":
    unittest.main()
