from pydantic import BaseModel

class BookingData(BaseModel):
    passenger_name:  str
    passenger_cnic:  str
    passenger_phone: str
    passenger_type:  str
    train_id:        int
    travel_date:     str
    selected_class:  str
    seat_label:      str
    payment_method:  str = "Visa"
    account_number:  str = ""
    payment_pin:     str = ""
    cvv:             str = ""
    card_last4:      str = ""
    card_expiry:     str = ""
    user_source:     str = ""
    user_destination:str = ""
    email_id:        str = ""
    full_name:       str = ""