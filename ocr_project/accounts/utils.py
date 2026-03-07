
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl

def send_email(sender_email, password, recipient_email, subject, body):
    try:
        # Create an SSL context
        context = ssl.create_default_context()
        context.set_ciphers("HIGH:!DH:!aNULL")

        # Set up the email details
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Attach the email body
        msg.attach(MIMEText(body, 'html'))

        # Connect to the SMTP server using port 587 with TLS
        server = smtplib.SMTP('smtp.rediffmailpro.com', 587)
        server.ehlo()
        server.starttls(context=context)

        print(f"Connecting to SMTP server...")
        # Log in to the server
        server.login(sender_email, password)
        print(f"Logged in successfully!")
        # Send the email
        server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"Email sent successfully to {recipient_email}!")

        # Disconnect from the server
        server.quit()
        return True

    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
    