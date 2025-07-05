import os

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

async def enviar_sms(numero: str, mensaje: str):
    if not TWILIO_ACCOUNT_SID:
        print(f"SMS (disabled): TO={numero}, MSG={mensaje[:50]}...")
        return False
    
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=mensaje,
            from_=TWILIO_PHONE_NUMBER,
            to=numero
        )
        
        print(f"SMS sent to {numero}: {message.sid}")
        return True
    except ImportError:
        print("Twilio not installed. Run: pip install twilio")
        return False
    except Exception as e:
        print(f"SMS error: {e}")
        return False