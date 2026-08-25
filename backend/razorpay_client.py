import os
from dotenv import load_dotenv
import razorpay

load_dotenv()

razorpay_key_id = os.getenv("RAZORPAY_KEY_ID")
razorpay_secret_key = os.getenv("RAZORPAY_KEY_SECRET")

client = razorpay.Client(auth=(razorpay_key_id, razorpay_secret_key))