from os import getenv
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
# account_sid = os.environ["TWILIO_ACCOUNT_SID"]
# auth_token = os.environ["TWILIO_AUTH_TOKEN"]
# client = Client(account_sid, auth_token)

def get_client() -> Client:
    # Twilio connection info
    TWILIO_API_KEY = getenv("TWILIO_API_KEY", None)
    TWILIO_API_SECRET = getenv("TWILIO_API_SECRET", None)
    # account_sid = getenv("TWILIO_ACCOUNT_SID", None)
    return Client(TWILIO_API_KEY, TWILIO_API_SECRET)


def low_glucose_alarm(client, owner_phone, call_from):
    call = client.calls.create(
        to=owner_phone,
        from_=call_from,
        twiml="""
            <Response>
                <Pause length="1.5"/>
                <Say voice="alice">
                    Warning: Your dog's glucose levels are becoming too low. Monitor immediately. 
                </Say>
                <Pause length="0.75"/>
                <Say voice="alice">
                    Warning: Your dog's glucose levels are becoming too low. Monitor immediately. 
                </Say>
                <Pause length="0.75"/>
            </Response>
        """
    )

    return call.sid


def high_glucose_alarm(client, owner_phone, call_from):
    call = client.calls.create(
        to=owner_phone,
        from_=call_from,
        twiml="""
            <Response>
                <Pause length="1.5"/>
                <Say voice="alice">
                    Warning: Your dog's glucose levels are becoming too high. Monitor immediately. 
                </Say>
                <Pause length="0.75"/>
                <Say voice="alice">
                    Warning: Your dog's glucose levels are becoming too high. Monitor immediately. 
                </Say>
                <Pause length="0.75"/>
            </Response>
        """
    )

    return call.sid



# client = get_client()
# low_glucose_alarm(client, getenv("OWNER_PHONE"), getenv("CALLER_PHONE"))