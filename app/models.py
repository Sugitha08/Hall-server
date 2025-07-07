from app.extension import db
from datetime import datetime

class Admin(db.Model):
    __tablename__ = 'admin_register'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    password = db.Column(db.String, nullable=False)


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile_number = db.Column(db.String(15), nullable=False)
    alt_mobile_number = db.Column(db.String(15))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))

class EventType(db.Model):
    __tablename__ = 'event_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'))
    event_type_id = db.Column(db.Integer, db.ForeignKey('event_types.id', ondelete='SET NULL'))
    total_amount = db.Column(db.Numeric(10, 2))
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)

class HoldDate(db.Model):
    __tablename__ = 'hold_date'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)

class EventSlot(db.Model):
    __tablename__ = 'event_slots'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'))
    event_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'))
    total_amt = db.Column(db.Numeric(10, 2))
    paid_amount = db.Column(db.Numeric(10, 2))
    paid_date = db.Column(db.Date)
    payment_status = db.Column(db.String(15))

class BookingDueDate(db.Model):
    __tablename__ = 'booking_due_dates'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False)
    remaining_amount = db.Column(db.Numeric(10, 2), nullable=False)
    expected_due_date = db.Column(db.Date, nullable=False)


class Transaction(db.Model):
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)
    trans_date = db.Column(db.Date)
    total_amt = db.Column(db.Numeric(10, 2))
    transaction_type = db.Column(db.String(15))
    description = db.Column(db.String(225))

class Notes(db.Model):
    __tablename__ = 'remainder'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    description = db.Column(db.String(225))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True)
    customer = db.relationship("Customer", backref="notes")

class Personal_Transaction(db.Model):
        __tablename__ = 'personal_transaction'
        id = db.Column(db.Integer, primary_key=True)
        trans_date = db.Column(db.Date)
        total_amt = db.Column(db.Numeric(10, 2))
        transaction_type = db.Column(db.String(15))
        description = db.Column(db.String(225))

class Personal_Notes(db.Model):
        __tablename__ = 'personal_remainder'
        id = db.Column(db.Integer, primary_key=True)
        date = db.Column(db.Date)
        description = db.Column(db.String(225))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustomerRecord(db.Model):
    __tablename__ = 'customer_record'

    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    image = db.Column(db.LargeBinary, nullable=False)
    mimetype = db.Column(db.String(50), nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
