from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token , jwt_required , get_jwt_identity
from sqlalchemy import false

from app.extension import db , scheduler , mail , limiter
from datetime import datetime ,date, timedelta , time
from app.models import Customer, Booking, EventSlot, Payment, EventType, Transaction, Notes, Personal_Transaction, \
    Personal_Notes, HoldDate, Admin, BookingDueDate, CustomerRecord
from flask_mail import Message
import pytz
from flask import current_app
import os
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError ,InvalidHashError
import base64
import random
import time as systime


ph = PasswordHasher()
auth = Blueprint('auth',__name__)
booking = Blueprint("event" , __name__)
accounts = Blueprint("accounts" , __name__)
notes = Blueprint("notes" , __name__)
personal = Blueprint("personal" , __name__)

# Temporary storage for OTPs (for testing, use DB or Cache in production)
otp_store = {}

OTP_EXPIRY_SECONDS = 120


@auth.route('/admin/register', methods=['POST'])
# @limiter.limit("5 per minute")  # Rate limit
def pub_register():    
    if Admin.query.first():
        return jsonify({"error": "Admin account already exists. Registration is closed."}), 403
     
    data = request.json
    required_fields = ["email", "password"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    if Admin.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already registered"}), 400

    hashed_password = ph.hash(data['password'])

    new_admin = Admin(
        email=data['email'],
        password=hashed_password,
    )
    db.session.add(new_admin)
    db.session.commit()

    return jsonify({"message": "Registration successful"}), 201


@auth.route('/admins', methods=['GET'])
def get_admins():
    admins = Admin.query.all()

    admin_list = []
    for admin in admins:
        admin_list.append({
            "email": admin.email,
            "password":admin.password
        })

    return jsonify({"admins": admin_list}), 200


@auth.route('/admin/count', methods=['GET'])
def get_admin_count():
    count = Admin.query.count()
    return jsonify({"count": count}), 200  


@auth.route('/login' , methods=['POST'])
# @limiter.limit("1 per week")
def login():
    data = request.json

    # Check if email and password exist in request
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"error": "Invalid credentials"}), 401

    admin = Admin.query.filter_by(email=data['email']).first()

    # Validate credentials
    if not admin:
        return jsonify({"error": "Invalid credentials"}), 401
    try:
        ph.verify(admin.password, data['password'])
    except InvalidHashError:
        return jsonify({"error": "Stored password is invalid. Please reset your password."}), 500
    except VerifyMismatchError:
        return jsonify({"error": "Invalid email or password"}), 401
    access_token = create_access_token(identity=str(admin.id))
    return jsonify({"access_token": access_token, "message": "Login successful"}), 200

@auth.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email')
    if not email:
        return jsonify({'message': 'Email required'}), 400
    
    admin = Admin.query.filter_by(email=email).first()
    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    otp = str(random.randint(1000, 9999))
    otp_store[email] = {'otp': otp, 'timestamp': systime.time()}   # Store OTP temporarily

    try:
        msg = Message('Your OTP for Password Reset', sender='your_email@gmail.com', recipients=[email])
        msg.body = f'Your OTP is {otp}'
        mail.send(msg)
        return jsonify({'message': 'OTP sent successfully'})
    except Exception as e:
        return jsonify({'message': 'Failed to send OTP', 'error': str(e)}), 500

@auth.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'message': 'Email and OTP required'}), 400
    
    otp_data = otp_store.get(email)

    if not otp_data:
        return jsonify({'message': 'OTP not found or expired'}), 400
    
    if systime.time() - otp_data['timestamp'] > OTP_EXPIRY_SECONDS:
        otp_store.pop(email, None)  # Remove expired OTP
        return jsonify({'message': 'OTP has expired'}), 400

    # Check OTP match
    if otp_data['otp'] == otp:
        otp_store.pop(email, None)  # Remove OTP after successful verification
        return jsonify({'message': 'OTP verified successfully'})
    else:
        return jsonify({'message': 'Invalid OTP'}), 400
    

@auth.route('/admin/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email')
    new_password = data.get('password')
    admin = Admin.query.filter_by(email=email).first()
    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    hashed_password = ph.hash(new_password)
    admin.password = hashed_password
    db.session.commit()

    return jsonify({"message": "Password reset successful"}), 200


@auth.route('/get/profile' , methods=['GET'])
@jwt_required()
def Get_Events():
     admin_id = get_jwt_identity()
     admin = Admin.query.get(admin_id)

     if not admin:
         return jsonify({"message":"Admin Not Found"}) , 404
     result = []
     for data in admin:
         result.append({
             "id": data.id,
             "email": data.email,
             "password":data.password
         })
     return jsonify({ "message": "Admin Data Successfully" ,"event_types" : result}), 200


@booking.route('/bookings', methods=['POST'])
@jwt_required()
def create_booking():
    data = request.json

    # 1. Create or fetch customer
    customer = Customer(
        name=data['customer_name'],
        mobile_number=data['mobile_number'],
        alt_mobile_number=data.get('alt_mobile_number') or None,
        email=data.get('email') or None,
        address=data['address'] or None
    )
    db.session.add(customer)
    db.session.flush()  # flush to get customer.id before commit



    # 3. Create slots
    for slot in data.get('slots', []):
        # 2. Create booking
        bookingEvent = Booking(
            customer_id=customer.id,
            event_type_id=data['event_type_id'],
            total_amount=data.get('total_amount')
        )
        db.session.add(bookingEvent)
        db.session.flush()
        db.session.add(EventSlot(
            booking_id=bookingEvent.id,
            event_date=datetime.strptime(slot['event_date'], '%Y-%m-%d').date(),
            start_time=datetime.strptime(slot['start_time'], '%I:%M %p').time(),
            end_time=datetime.strptime(slot['end_time'], '%I:%M %p').time()
        ))
        due_dates = data.get('dueDates', [])
        total_remaining = 0

        for item in due_dates:
            remaining = item.get('remaining_amount')
            amt = float(remaining) if remaining is not None else 0.0
            total_remaining += amt

        payment_status = "Pending" if total_remaining > 0 else "Paid"

        # 4. Create payment
        payment = Payment(
            booking_id=bookingEvent.id,
            total_amt=data.get('total_amount'),
            paid_amount=data['paid_amount'],
            paid_date=datetime.strptime(data['paid_date'], '%Y-%m-%d').date(),
            payment_status=payment_status,
        )
        db.session.add(payment)

        for slot in due_dates:
            expected_due_date_str = slot.get('expected_due_date')
            if expected_due_date_str:
                expected_due_date = datetime.strptime(expected_due_date_str, '%Y-%m-%d').date()
            else:
                expected_due_date = None

            db.session.add(BookingDueDate(
                booking_id=bookingEvent.id,
                expected_due_date=expected_due_date,
                remaining_amount=data['remaining_amount'],
            ))


    if data.get("dueDates"):
        for dates in data.get("dueDates"):
            expected_due_date_str = dates.get('expected_due_date')

            if isinstance(expected_due_date_str, str):
                expected_due_date = datetime.strptime(expected_due_date_str, '%Y-%m-%d').date()
            else:
                expected_due_date = expected_due_date_str  # You can also raise an error or skip

            if expected_due_date:
                description = f"{data['customer_name']}'s due Date is on {expected_due_date}"
                note_date = expected_due_date  # ✅ No need to parse again
                remainder = Notes(date=note_date, description=description , customer_id =customer.id )
                db.session.add(remainder)
                db.session.commit()

                # Schedule reminder
                schedule_reminder(description, expected_due_date, scheduler, send_reminder_email)


    # 4. Create transcation
    transaction = Transaction(
        trans_date=datetime.strptime(data['paid_date'], '%Y-%m-%d').date(),
        total_amt=data.get('paid_amount'),
        transaction_type='credit',
        description=f"{data['customer_name']} event"
    )
    db.session.add(transaction)



    db.session.commit()

    return jsonify({"message": "Booking created successfully "}), 201

@booking.route('/bookings/cancel/<int:booking_id>', methods=['DELETE'])
@jwt_required()
def delete_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({"message": "Booking not found"}), 404
    customer_id = booking.customer_id

    # 2. You want to check if this customer has other bookings
    other_bookings = Booking.query.filter(
         Booking.customer_id == customer_id,
        Booking.id != booking_id
    ).count()

    if other_bookings > 0:
        print(f"Customer has {other_bookings} other booking(s).")
    else:
        print(f"Customer has no other booking(s).")
        notes = Notes.query.filter_by(customer_id=customer_id).all()
        print(notes)
        for note in notes:
            db.session.delete(note)
            db.session.commit()

        # Delete associated EventSlots
    EventSlot.query.filter_by(booking_id=booking_id).delete()
    db.session.delete(booking)

    db.session.commit()

    return jsonify({"message": "Event Cancelled Succesfully"}), 200


@booking.route('/holddate' , methods=['POST'])
@jwt_required()
def hold_date():
    data = request.json

    # Check if email and password exist in request
    if not data or 'date' not in data or 'description' not in data:
        return jsonify({"error": "Missing Required Field"}), 400

    hold_date = HoldDate(
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        name=data.get('name'),
        description=data['description']
    )
    db.session.add(hold_date)
    db.session.commit()

    return jsonify({ "message": "Date Hold successful"}), 200

@booking.route('/holddate/cancel/<int:id>' , methods=['DELETE'])
@jwt_required()
def delete_hold_date(id):
    hold_date = HoldDate.query.get(id)
    if not hold_date:
        return jsonify({"message": "Hold Date not found"}), 404

    db.session.delete(hold_date)
    db.session.commit()

    return jsonify({ "message": "Cancel Hold Date successful"}), 200

@booking.route('/calendar/<int:year>', methods=['GET'])
@jwt_required()
def calendar_view(year):
    start_of_year = date(year, 1, 1)
    end_of_year = date(year, 12, 31)

    # Query all event slots within the year
    slots = EventSlot.query.filter(
        EventSlot.event_date >= start_of_year,
        EventSlot.event_date <= end_of_year
    ).all()

    Hold_slots = HoldDate.query.filter(
        HoldDate.date >= start_of_year,
        HoldDate.date <= end_of_year
    ).all()

    # Booked events info
    booked_events = []
    for slot in slots:
        bookingDetails = Booking.query.filter_by(id=slot.booking_id).first()
        customer = Customer.query.filter_by(id=bookingDetails.customer_id).first()
        payment = Payment.query.filter_by(booking_id=slot.booking_id).first()
        event = EventType.query.filter_by(id=bookingDetails.event_type_id).first()
        booked_events.append({
            'booking_id': slot.booking_id,
            'event_date': slot.event_date.isoformat(),
            'start_time': slot.start_time.strftime('%I:%M %p') if slot.start_time else None,
            'end_time': slot.end_time.strftime('%I:%M %p') if slot.end_time else None,
            'event_type': event.name,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'mobile_number': customer.mobile_number,
                'email': customer.email,
                'address': customer.address,
                "payment_status":payment.payment_status,
                "Paid_amount" : payment.paid_amount
            } if customer else None
        })

    Hold_events = []
    for slot in Hold_slots:
        Hold_events.append({
            'id': slot.id,
            'event_date': slot.date.isoformat()
        })

    return jsonify({
        'year': year,
        'booked_events': booked_events,
        'Hold_events':Hold_events
    })


@booking.route('/check-date', methods=['GET'])
@jwt_required()
def check_event_date():
    date_str = request.args.get('event_date')

    # Validate input
    if not date_str:
        return jsonify({"error": "Missing event_date parameter"}), 400

    try:
        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Check if the date exists in the EventSlot table
    slot = EventSlot.query.filter_by(event_date=event_date).first()
    booked_event = {}
    if(slot):
        bookingDetails = Booking.query.filter_by(id=slot.booking_id).first()
        customer = Customer.query.filter_by(id=bookingDetails.customer_id).first()
        payment = Payment.query.filter_by(booking_id=slot.booking_id).first()
        event = EventType.query.filter_by(id=bookingDetails.event_type_id).first()
        booked_event ={
                'booking_id': slot.booking_id,
                'event_date': slot.event_date.isoformat(),
                'start_time': slot.start_time.strftime('%I:%M %p') if slot.start_time else None,
                'end_time': slot.end_time.strftime('%I:%M %p') if slot.end_time else None,
                'event_type': event.name,
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'mobile_number': customer.mobile_number,
                    'email': customer.email,
                    'address': customer.address,
                    "payment_status": payment.payment_status,
                    "paid_amount":payment.paid_amount
                } if customer else None
            }
        return jsonify({
            "event_date": event_date.isoformat(),
            "is_booked": True,
            'isDateHoled': False,
            "BookedDetails": booked_event
        }), 200

        # Check if the date exists in the EventSlot table
    hold = HoldDate.query.filter_by(date=event_date).first()
    holded_event = {}
    if (hold):
        holded_event = {
            'event_date': hold.date.isoformat(),
            'name' : hold.name,
            'description':hold.description
        }
        return jsonify({
            "event_date": event_date.isoformat(),
            "is_booked": False,
            'isDateHoled' : True,
            "BookedDetails": holded_event
        }), 200

    else:
        return jsonify({
            "event_date": event_date.isoformat(),
            "is_booked": False,
            'isDateHoled': False,
            "message": "No event slot found for this date."
        }), 200

@booking.route('/event_types' , methods=['GET'])
# @jwt_required()
def Get_Events():
     events = EventType.query.all()
     result = []
     for event in events:
         result.append({
             "id": event.id,
             "name": event.name,
         })
     return jsonify({ "message": "Event Type Fetched Successfully" ,"event_types" : result}), 200

@booking.route('/add/event_types', methods=['POST'])
# @jwt_required()
def add_event():
    data = request.json

    # Validate incoming data
    if not data or 'name' not in data:
        return jsonify({"error": "Event name is required"}), 400

    # Optional: Check for duplicate event name
    existing_event = EventType.query.filter_by(name=data['name']).first()
    if existing_event:
        return jsonify({"error": "Event type already exists"}), 409

    # Create and save new event type
    new_event = EventType(name=data['name'])
    db.session.add(new_event)
    db.session.commit()

    return jsonify({
        "message": "Event type added successfully",
        "event_type": {
            "id": new_event.id,
            "name": new_event.name
        }
    }), 201



@accounts.route('/create_trans' , methods=['POST'])
@jwt_required()
def account_details():
    data = request.json
    transaction_type = data.get('transaction_type')

    for transaction in data.get('paymentDetails', []):
        db.session.add(Transaction(
            trans_date=datetime.strptime(transaction['date'], '%Y-%m-%d').date(),
            total_amt=transaction['total_amount'],
            transaction_type=transaction_type,
            description=transaction['description'],
        ))

    db.session.commit()

    return jsonify({"message": "Transaction Added successfully "}), 201


@accounts.route('/edit_trans/<int:trans_id>', methods=['PUT'])
@jwt_required()
def edit_transaction(trans_id):
    transaction = Transaction.query.get(trans_id)
    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404

    data = request.json

    if 'date' in data:
        transaction.trans_date = datetime.strptime(data['date'], '%Y-%m-%d').date()

    if 'total_amount' in data:
        transaction.total_amt = data['total_amount']

    if 'transaction_type' in data:
        transaction.transaction_type = data['transaction_type']

    if 'description' in data:
        transaction.description = data['description']

    db.session.commit()

    return jsonify({"message": "Transaction updated successfully"}), 200

@accounts.route('/delete_trans/<int:trans_id>', methods=['DELETE'])
@jwt_required()
def delete_transaction(trans_id):
    transaction = Transaction.query.get(trans_id)

    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404
    db.session.delete(transaction)
    db.session.commit()

    return jsonify({"message": "Transaction deleted successfully"}), 200

@accounts.route('/get_trans/<int:year>/<int:month>' , methods=['GET'])
@jwt_required()
def get_account_details(year , month):
    # Validate month
    if month < 1 or month > 12:
        return jsonify({"message": "Invalid month"}), 400

    start_of_month = date(year, month, 1)

    # Calculate the last day of the month
    if month == 12:
        end_of_month = date(year, 12, 31)
    else:
        end_of_month = date(year, month + 1, 1) - timedelta(days=1)

    # Query transactions within the month
    all_trans = Transaction.query.filter(
        Transaction.trans_date >= start_of_month,
        Transaction.trans_date <= end_of_month
    ).all()

    total_credit = 0
    total_debit = 0

    result = []
    for trans in all_trans:
        result.append({
            "id": trans.id,
            "date": trans.trans_date,
            "trans_amt" : trans.total_amt,
            "description" :trans.description,
            "trans_type" : trans.transaction_type
        })
        if trans.transaction_type.lower() == "credit":
            total_credit += trans.total_amt
        elif trans.transaction_type.lower() == "debit":
            total_debit += trans.total_amt
    return jsonify({"message": "Transaction Fetched successfully","transactions":result, "total_credit": total_credit,
        "total_debit": total_debit}), 200


def schedule_reminder(description, resdate, scheduler, callback_func):
    # Parse the date
    if isinstance(resdate, str):
        note_date = datetime.strptime(resdate, "%Y-%m-%d").date()
    else:
        note_date = resdate

    # Calculate reminder date (7 day before)
    reminder_date = note_date - timedelta(days=7)

    # Set reminder time to 9:00 AM IST
    reminder_datetime = datetime.combine(reminder_date, time(hour=9, minute=0))
    ist = pytz.timezone("Asia/Kolkata")
    reminder_datetime = ist.localize(reminder_datetime)

    # Generate unique job ID
    job_id = f"reminder_{description[:10]}_{resdate}"

    # Schedule the job
    scheduler.add_job(
        id=job_id,
        func=callback_func,
        trigger="date",
        run_date=reminder_datetime,
        args=[current_app._get_current_object(), description],
        replace_existing=True,
        misfire_grace_time=3600 * 6,  # 6 hours
        coalesce=True
    )


# Function to send email
def send_reminder_email(app,description):
  with app.app_context():
    print("🚀 Sending email:", description)
    msg = Message(
        subject="Reminder: Upcoming Remainder",
        sender=os.environ.get('MAIL_USERNAME'),
        recipients=[os.environ.get('MAIL_DEFAULT_SENDER')],
        body=f"Remainder: {description}"
    )
    mail.send(msg)

# API endpoint to add a note and schedule a reminder
@notes.route("/remainder", methods=["POST"])
@jwt_required()
def add_note():
    data = request.json
    resdate = data.get("date")
    description = data.get("description")

    try:
        # Save note to DB
        note_date = datetime.strptime(resdate, '%Y-%m-%d').date()
        remainder = Notes(date=note_date, description=description)
        db.session.add(remainder)
        db.session.commit()

        # Call the reusable reminder function
        schedule_reminder(description, resdate, scheduler, send_reminder_email)

        return jsonify({"message": "Note added and reminder scheduled!"}), 201

    except Exception as e:
        return jsonify({"message": str(e)}), 500

@notes.route("/delremainder/<int:note_id>", methods=["DELETE"])
@jwt_required()
def delete_note(note_id):
    try:
        note = Notes.query.get(note_id)
        if not note:
            return jsonify({"message": "Note not found"}), 404

        db.session.delete(note)
        db.session.commit()

        return jsonify({"message": "Note deleted successfully"}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

@notes.route("/remainder/get/<int:year>/<int:month>", methods=["GET"])
@jwt_required()
def get_note(year , month):
   try:
       # Validate month
     if month < 1 or month > 12:
       return jsonify({"message": "Invalid month"}), 400
     today = date.today()
     start_of_month = date(year, month, 1)

       # Calculate the last day of the month
     if month == 12:
        end_of_month = date(year, 12, 31)
     else:
        end_of_month = date(year, month + 1, 1) - timedelta(days=1)

     # Query transactions within the month
     remainders = Notes.query.filter(
           Notes.date >= today,
           Notes.date >= start_of_month,
           Notes.date <= end_of_month
     ).all()
     result = []
     for event in remainders:
         result.append({
             "id": event.id,
             "date": event.date,
             "description" : event.description
         })
     return jsonify({"message": "reminder scheduled Fetched Successfully!","remainders":result}), 200

   except Exception as e:
       return jsonify({"message": f"Error: {str(e)}"}), 500



@booking.route('/upload-image', methods=['POST'])
@jwt_required()
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    customer_name = request.form.get('name')
    event_date = request.form.get('date')
    if not all([event_date, customer_name]):
        return jsonify({"error": "Missing required fields"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    new_image = CustomerRecord(
        customer_name=customer_name,  # or get from your form data
        image=file.read(),
        mimetype=file.mimetype,
        event_date=event_date,
    )
    db.session.add(new_image)
    db.session.commit()
    return jsonify({'message': 'Image uploaded successfully'}), 201


@booking.route('/getrecord', methods=['GET'])
@jwt_required()
def get_image():
    event_date = request.args.get('event_date')

    if not event_date:
        return jsonify({'error': 'event_date is required'}), 400

    image_record = CustomerRecord.query.filter_by(event_date=event_date).first()
    if not image_record:
        return jsonify({'message': 'Event not found' , 'status':False}), 200

    # Convert image binary to base64 string
    encoded_image = base64.b64encode(image_record.image).decode('utf-8')

    return jsonify({
        'image': f"data:{image_record.mimetype};base64,{encoded_image}",
        'customer_name': image_record.customer_name,
        'event_date': image_record.event_date.strftime('%Y-%m-%d %H:%M:%S'),
        'upload_date': image_record.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
        'message': 'Event Held',
        'status': True
    }), 200


# PERSONAL ROUTES

@personal.route('/create_trans' , methods=['POST'])
@jwt_required()
def personal_account_details():
    data = request.json
    transaction_type = data.get('transaction_type')

    for transaction in data.get('paymentDetails', []):
        db.session.add(Personal_Transaction(
            trans_date=datetime.strptime(transaction['date'], '%Y-%m-%d').date(),
            total_amt=transaction['total_amount'],
            transaction_type=transaction_type,
            description=transaction['description'],
        ))

    db.session.commit()

    return jsonify({"message": "Transaction Added successfully "}), 201

@personal.route('/edit_trans/<int:trans_id>', methods=['PUT'])
@jwt_required()
def edit_Ptransaction(trans_id):
    transaction = Personal_Transaction.query.get(trans_id)
    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404

    data = request.json

    if 'date' in data:
        transaction.trans_date = datetime.strptime(data['date'], '%Y-%m-%d').date()

    if 'total_amount' in data:
        transaction.total_amt = data['total_amount']

    if 'transaction_type' in data:
        transaction.transaction_type = data['transaction_type']

    if 'description' in data:
        transaction.description = data['description']

    db.session.commit()

    return jsonify({"message": "Transaction updated successfully"}), 200

@personal.route('/delete_trans/<int:trans_id>', methods=['DELETE'])
@jwt_required()
def delete_Ptransaction(trans_id):
    transaction = Personal_Transaction.query.get(trans_id)

    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404
    db.session.delete(transaction)
    db.session.commit()

    return jsonify({"message": "Transaction deleted successfully"}), 200


@personal.route('/get_trans/<int:year>/<int:month>' , methods=['GET'])
@jwt_required()
def getpersonal_account_details(year , month):
    # Validate month
    if month < 1 or month > 12:
        return jsonify({"message": "Invalid month"}), 400

    start_of_month = date(year, month, 1)

    # Calculate the last day of the month
    if month == 12:
        end_of_month = date(year, 12, 31)
    else:
        end_of_month = date(year, month + 1, 1) - timedelta(days=1)

    # Query transactions within the month
    all_trans = Personal_Transaction.query.filter(
        Personal_Transaction.trans_date >= start_of_month,
        Personal_Transaction.trans_date <= end_of_month
    ).all()

    print(all_trans)

    total_credit = 0
    total_debit = 0

    result = []
    for trans in all_trans:
        result.append({
            "id": trans.id,
            "date": trans.trans_date,
            "trans_amt" : trans.total_amt,
            "description" :trans.description,
            "trans_type" : trans.transaction_type
        })
        if trans.transaction_type.lower() == "credit":
            total_credit += trans.total_amt
        elif trans.transaction_type.lower() == "debit":
            total_debit += trans.total_amt
    return jsonify({"message": "Transaction Fetched successfully","transactions":result, "total_credit": total_credit,
        "total_debit": total_debit}), 200


@personal.route("/remainder", methods=["POST"])
@jwt_required()
def addPersonal_note():
    data = request.json
    resdate = data.get("date")
    description = data.get("description")

    try:
        # Save note to DB
        note_date = datetime.strptime(resdate, '%Y-%m-%d').date()
        remainder = Personal_Notes(date=note_date, description=description)
        db.session.add(remainder)
        db.session.commit()

        # Parse the original date (string format: "YYYY-MM-DD")
        note_date = datetime.strptime(resdate, "%Y-%m-%d").date()

        # Calculate reminder date (1 day before)
        reminder_date = note_date - timedelta(days=1)
        # Set time to 9:00 AM
        reminder_datetime = datetime.combine(reminder_date, time(hour=9, minute=0))
        # Localize to IST
        ist = pytz.timezone("Asia/Kolkata")
        reminder_datetime = ist.localize(reminder_datetime)
        # Generate unique job ID
        job_id = f"reminder_{description[:10]}_{resdate}"
        # Schedule the job with misfire handling
        scheduler.add_job(
            id=job_id,
            func=send_reminder_email,
            trigger="date",
            run_date=reminder_datetime,
            args=[current_app._get_current_object(), description],
            replace_existing=True,
            misfire_grace_time=3600 * 6,  # 6 hours grace
            coalesce=True
        )

        return jsonify({"message": "Note added and reminder scheduled!"}), 201

    except Exception as e:
        return jsonify({"message": str(e)}), 500

@personal.route("/delremainder/<int:note_id>", methods=["DELETE"])
@jwt_required()
def delete_Pnote(note_id):
    try:
        note = Personal_Notes.query.get(note_id)
        if not note:
            return jsonify({"message": "Note not found"}), 404

        db.session.delete(note)
        db.session.commit()

        return jsonify({"message": "Note deleted successfully"}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

@personal.route("/remainder/get/<int:year>/<int:month>", methods=["GET"])
@jwt_required()
def getPersonal_note(year , month):
   try:
    # Validate month
     if month < 1 or month > 12:
        return jsonify({"message": "Invalid month"}), 400

     today = date.today()
     start_of_month = date(year, month, 1)

     # Calculate the last day of the month
     if month == 12:
        end_of_month = date(year, 12, 31)
     else:
        end_of_month = date(year, month + 1, 1) - timedelta(days=1)

       # Query transactions within the month
     remainders = Personal_Notes.query.filter(
        Personal_Notes.date >= today,
        Personal_Notes.date >= start_of_month,
        Personal_Notes.date <= end_of_month
     ).all()

     result = []
     for event in remainders:
         result.append({
             "id": event.id,
             "date": event.date,
             "description" : event.description
         })
     return jsonify({"message": "reminder scheduled Fetched Successfully!","remainders":result}), 200

   except Exception as e:
       return jsonify({"message": f"Error: {str(e)}"}), 500




