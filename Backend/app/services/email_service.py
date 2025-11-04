def send_otp_email(email: str, otp: int):
    # For demo, just print. In production, integrate SMTP / SendGrid.
    print(f"Sending OTP {otp} to email {email}")

