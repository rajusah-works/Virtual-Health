from flask import Flask, request, render_template, session, url_for, redirect
from flask import make_response
from xhtml2pdf import pisa
from io import BytesIO
from flask_sqlalchemy import SQLAlchemy
import numpy as np
import cv2
import os
import sys
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
from keras.models import load_model
from PIL import Image
import warnings
import json
import logging
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


# Suppress warning
warnings.filterwarnings("ignore", category=UserWarning, message="Trying to unpickle estimator")

tf.get_logger().setLevel(logging.ERROR)

from src.exception import CustomException
from src.logger import logging as lg
from src.disease_prediction.disease_prediction import DiseasePrediction
from src.alternativedrug.AlternativeDrug import AlternateDrug
from src.Prediction.disease_predictions import ModelPipeline
from src.Insurance.Insurance import Insurance_Prediction
#from src.ImagePrediction.image_prediction import ImagePrediction
# from src.DrugResponse.drugresponse import report_generator
from src.llm_report.Report import report_generator
# from src.Food.food import food_report_generator


current_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///"+os.path.join(current_dir, "database2.sqlite3")
app.config['SECRET_KEY'] = 'healthmap'
db = SQLAlchemy()
db.init_app(app)
app.app_context().push()

class Symptoms(db.Model):
    __tablename__ = 'symptoms'
    id = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, unique=True)
    fname = db.Column(db.String(30), nullable=False)
    lname = db.Column(db.String(30), nullable=False)
    phone = db.Column(db.String(13), nullable=False)
    email = db.Column(db.String(40), nullable=False)
    symp1 = db.Column(db.String(30), nullable=False)
    symp2 = db.Column(db.String(30))
    symp3 = db.Column(db.String(30))
    symp4 = db.Column(db.String(30))


class Precautions(db.Model):
    __tablename__ = 'precautions'
    sl = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, unique=True)
    p_id = db.Column(db.Integer, db.ForeignKey("symptoms.id"), nullable=False)
    precaution = db.Column(db.String(30), nullable=False)

class Medications(db.Model):
    __tablename__ = 'medications'
    sl = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, unique=True)
    m_id = db.Column(db.Integer, db.ForeignKey("symptoms.id"), nullable=False)
    medication = db.Column(db.String(30), nullable=False)

class Disease(db.Model):
    __tablename__ = 'disease'
    sl = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, unique=True)
    d_id = db.Column(db.Integer, db.ForeignKey("symptoms.id"), nullable=False)
    disease = db.Column(db.String(30), nullable=False)

class Diet(db.Model):
    __tablename__ = 'diet'
    sl = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, unique=True)
    di_id = db.Column(db.Integer, db.ForeignKey("symptoms.id"), nullable=False)
    diet = db.Column(db.String(30), nullable=False)

class Workout(db.Model):
    __tablename__ = 'workout'
    sl = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, unique=True)
    w_id = db.Column(db.Integer, db.ForeignKey("symptoms.id"), nullable=False)
    workout = db.Column(db.String(30), nullable=False)

class Description(db.Model):
    __tablename__ = 'description'
    sl = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=True, unique=True)
    des_id = db.Column(db.Integer, db.ForeignKey("symptoms.id"), nullable=False)
    description = db.Column(db.String(200), nullable=False)


@app.route("/")
def index():
    return render_template("index.html")

@app.route('/home')
def home():
    return render_template("index.html")

with open('src/datasets/symptoms.json', 'r') as json_file:
    symptoms_dict = json.load(json_file)
with open('src/datasets/disease_list.json', 'r') as json_file:
    diseases_list = json.load(json_file)

@app.route("/disease")
def disease():
    return render_template("disease.html", symptoms_dict=symptoms_dict)

@app.route('/developer')
def developer():
    return render_template("developer.html")

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    try:
        if request.method == 'POST':
            fname = request.form.get('fname')
            lname = request.form.get('lname')
            phone = request.form.get('phone')
            email = request.form.get('email')
            symptom_1 = request.form.get('symptom_1')
            symptom_2 = request.form.get('symptom_2')
            symptom_3 = request.form.get('symptom_3')
            symptom_4 = request.form.get('symptom_4')
            symptoms_list = [symptom_1, symptom_2, symptom_3, symptom_4]
            
            symp_list = Symptoms(fname=fname, lname=lname, phone=phone, email=email, symp1 = symptom_1, symp2 = symptom_2, symp3 = symptom_3, symp4 = symptom_4)
            db.session.add(symp_list)
            db.session.commit()

            symptom_id = symp_list.id

            model = DiseasePrediction()
            predicted_disease, dis_des, my_precautions, medications, rec_diet, rec_workout, symptoms_dict = model.predict(symptoms_list=symptoms_list)

            for precaution in my_precautions:
                if precaution and isinstance(precaution, str):
                    precaution_entry = Precautions(p_id=symptom_id, precaution=precaution)
                    db.session.add(precaution_entry)
            db.session.commit()

            for medication in medications:
                if medication and isinstance(medication, str):
                    med_items = [item.strip().strip("'\"") for item in medication.strip("[]").split(",")]
                    for med in med_items:
                        medication_entry =Medications(m_id=symptom_id, medication=med)
                        db.session.add(medication_entry)
            db.session.commit()

            if predicted_disease and isinstance(predicted_disease, str):
                disease_entry = Disease(d_id=symptom_id, disease=predicted_disease)
                db.session.add(disease_entry)
                db.session.commit()


            if dis_des and isinstance(dis_des, str):
                    description_entry =Description(des_id=symptom_id, description=dis_des)
                    db.session.add(description_entry)
            db.session.commit()

            for workout in rec_workout:
                if workout and isinstance(workout, str):
                    workout_entry =Workout(w_id=symptom_id, workout=workout)
                    db.session.add(workout_entry)
            db.session.commit()

            for diet in rec_diet:
                if diet and isinstance(diet, str):
                    diet_items = [item.strip().strip("'\"") for item in medication.strip("[]").split(",")]
                    for item in diet_items:
                        diet_entry =Diet(di_id=symptom_id, diet=item)
                        db.session.add(diet_entry)
            db.session.commit()


            # print(medications)


            return render_template('disease.html', predicted_disease=predicted_disease, dis_des=dis_des,
                                   my_precautions=my_precautions, medications=med_items, my_diet=diet_items,
                                   my_workout=rec_workout, symptoms_dict=symptoms_dict,)
        return render_template('disease.html', symptoms_dict=symptoms_dict,fname=fname,lname=lname,phone=phone,email=email)
    except Exception as e:
        lg.error(f"Error in /predict route: {e}")
        raise CustomException(e, sys)

@app.route("/data")
def data():
    user_data = Symptoms.query.all()
    disease=Disease.query.all()
    description=Description.query.all()
    precautions = Precautions.query.all()
    medications=Medications.query.all()
    workout=Workout.query.all()
    diet=Diet.query.all()

    return render_template("doctors.html", user_data=user_data,disease=disease,description=description, precautions=precautions, medications=medications,workout=workout,diet=diet)


@app.route("/patient/<email>")
def patient(email):
    # email = Symptoms.email()
    user_data = Symptoms.query.filter_by(email=email).all()
    disease=Disease.query.all()
    description=Description.query.all()
    precautions = Precautions.query.all()
    medications=Medications.query.all()
    workout=Workout.query.all()
    diet=Diet.query.all()

    return render_template("patient.html", email=email, user_data=user_data,disease=disease,description=description, precautions=precautions,medications=medications,workout=workout,diet=diet)


@app.route("/download_report/<int:patient_id>")
def download_report(patient_id):
    try:
        # Fetch patient data
        user_data = Symptoms.query.filter_by(id=patient_id).first()
        disease = Disease.query.filter_by(d_id=patient_id).all()
        description = Description.query.filter_by(des_id=patient_id).all()
        precautions = Precautions.query.filter_by(p_id=patient_id).all()
        medications = Medications.query.filter_by(m_id=patient_id).all()
        workout = Workout.query.filter_by(w_id=patient_id).all()
        diet = Diet.query.filter_by(di_id=patient_id).all()

        # Render the HTML template with context
        html = render_template(
            "reportpdf.html",
            user_data=[user_data],
            disease=disease,
            description=description,
            precautions=precautions,
            medications=medications,
            workout=workout,
            diet=diet,
        )

        # Convert HTML to PDF
        pdf = BytesIO()
        pisa_status = pisa.CreatePDF(BytesIO(html.encode("utf-8")), pdf)
        
        if pisa_status.err:
            return "Error generating PDF", 500

        # Send PDF as a response
        response = make_response(pdf.getvalue())
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f"attachment; filename={user_data.fname}_{user_data.lname}_Report.pdf"
        return response
    except Exception as e:
        lg.error(f"Error generating report: {e}")
        raise CustomException(e, sys)




@app.route("/findpatient")
def findpatient():
    return render_template("findpatient.html")


@app.route("/update_precaution", methods=['POST'])
def update_precaution():
    precaution_id = request.form.get('precaution_id')
    new_precaution = request.form.get('new_precaution')
    
    precaution = Precautions.query.filter_by(sl=precaution_id).first()
    if precaution:
        precaution.precaution = new_precaution
        db.session.commit()

    return redirect(url_for('data'))

@app.route("/update_medication", methods=['POST'])
def update_medication():
    medication_id = request.form.get('medication_id')
    new_medication = request.form.get('new_medication')
    print(f"Medication ID: {medication_id}")
    print(f"New Medication: {new_medication}")
    
    medication = Medications.query.filter_by(sl=medication_id).first()
    if medication:
        medication.medication = new_medication
        db.session.commit()

    return redirect(url_for('data'))

@app.route("/update_disease", methods=['POST'])
def update_disease():
    disease_id = request.form.get('disease_id')
    new_disease = request.form.get('new_disease')
    
    print(f"Disease ID: {disease_id}")
    print(f"New Disease: {new_disease}")

    # Fetch the disease record using the provided id
    disease = Disease.query.filter_by(sl=disease_id).first()
    
    if disease:
        disease.disease = new_disease  # Update the disease field
        db.session.commit()  # Commit the changes to the database
        print("Disease updated successfully")
    else:
        print("Disease not found")

    return redirect(url_for('data'))


    return redirect(url_for('data'))

@app.route("/update_description", methods=['POST'])
def update_description():
    description_id = request.form.get('description_id')
    new_description = request.form.get('new_description')
    
    description = Description.query.filter_by(sl=description_id).first()
    if description:
        description.description = new_description
        db.session.commit()

    return redirect(url_for('data'))

@app.route("/update_workout", methods=['POST'])
def update_workout():
    workout_id = request.form.get('workout_id')
    new_workout = request.form.get('new_workout')
    print(f"workout ID: {workout_id}")
    print(f"New workout: {new_workout}")
    
    workout = Workout.query.filter_by(sl=workout_id).first()
    if workout:
        workout.workout = new_workout
        db.session.commit()

    return redirect(url_for('data'))

@app.route("/update_diet", methods=['POST'])
def update_diet():
    diet_id = request.form.get('diet_id')
    new_diet = request.form.get('new_diet')
    
    diet = Diet.query.filter_by(sl=diet_id).first()
    if diet:
        diet.diet = new_diet
        db.session.commit()
    return redirect(url_for('data'))

@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/drugresponse', methods=['GET', 'POST'])
def drugresponse():
    try:
        with open('src/datasets/side_effects.json', 'r') as file:
            side_effects_data = json.load(file)
        side_effects = None
        if request.method == 'POST':
            drug_name = request.form.get('drug_name')
            side_effects = side_effects_data.get(drug_name, "No data available for this drug.")
        return render_template("drug_response.html", side_effects=side_effects)
    except Exception as e:
        lg.error(f"Error in /drugresponse route: {e}")
        raise CustomException(e, sys)

@app.route('/alternativedrug', methods=['GET', 'POST'])
def alternativedrug():
    try:
        if request.method == 'POST':
            selected_medicine = request.form['medicine']
            alt = AlternateDrug()
            recommendations, medicines_data = alt.recommendation(selected_medicine)  
            return render_template("alternativedrug.html", medicines=medicines_data, prediction_text=recommendations)
        else:
            alt = AlternateDrug()
            medicines_data = alt.medi()
            return render_template("alternativedrug.html", medicines=medicines_data)
    except Exception as e:
        lg.error(f"Error in /alternativedrug route: {e}")
        raise CustomException(e, sys)

@app.route('/liver', methods=['GET', 'POST'])
def liver():
    try:
        if request.method == 'POST':
            to_predict_dict = request.form.to_dict()
            model = ModelPipeline()
            pred = model.liver_predict(to_predict_dict)
            return render_template("liver.html", prediction_text_liver=pred)
        else:
            return render_template("liver.html")
    except Exception as e:
        lg.error(f"Error in /liver route: {e}")
        raise CustomException(e, sys)

@app.route('/breast', methods=['GET', 'POST'])
def breast():
    try:
        if request.method == 'POST':
            to_predict_dict = request.form.to_dict()
            model = ModelPipeline()
            pred = model.breast_cancer_predict(to_predict_dict)
            return render_template("breast.html", prediction_text=pred)
        else:
            return render_template("breast.html")
    except Exception as e:
        lg.error(f"Error in /breast route: {e}")
        raise CustomException(e, sys)

@app.route('/diabetes', methods=['GET', 'POST'])
def diabetes():
    try:
        if request.method == 'POST':
            to_predict_dict = request.form.to_dict()
            model = ModelPipeline()
            pred = model.diabetes_predict(to_predict_dict)
            return render_template("diabetes.html", prediction_text=pred)
        else:
            return render_template("diabetes.html")
    except Exception as e:
        lg.error(f"Error in /diabetes route: {e}")
        raise CustomException(e, sys)

@app.route('/heart', methods=['GET', 'POST'])
def heart():
    try:
        if request.method == 'POST':
            to_predict_dict = request.form.to_dict()
            model = ModelPipeline()
            pred = model.heart_predict(form_data=to_predict_dict)
            return render_template("heart.html", prediction_text=pred)
        else:
            return render_template("heart.html")
    except Exception as e:
        lg.error(f"Error in /heart route: {e}")
        raise CustomException(e, sys)

@app.route('/kidney', methods=['GET', 'POST'])
def kidney():
    try:
        if request.method == 'POST':
            to_predict_dict = request.form.to_dict()
            model = ModelPipeline()
            pred = model.kidney_predict(to_predict_dict)
            return render_template("kidney.html", prediction_text=pred)
        else:
            return render_template("kidney.html")
    except Exception as e:
        lg.error(f"Error in /kidney route: {e}")
        raise CustomException(e, sys)

@app.route('/parkinsons', methods=['GET', 'POST'])
def parkinsons():
    try:
        if request.method == 'POST':
            to_predict_dict = request.form.to_dict()
            model = ModelPipeline()
            pred = model.parkinsons_predict(to_predict_dict)
            return render_template("parkinsons.html", prediction_text=pred)
        else:
            return render_template("parkinsons.html")
    except Exception as e:
        lg.error(f"Error in /parkinsons route: {e}")
        raise CustomException(e, sys)

@app.route('/insurance', methods=['GET', 'POST'])
def insurance():
    try:
        if request.method == 'POST':
            form_data = request.form.to_dict()
            model = Insurance_Prediction()
            policy, policy_price = model.insurance_predict(form_data=form_data)
            return render_template("insurance.html", policy=policy, policy_price=policy_price)
        else:
            return render_template("insurance.html")
    except Exception as e:
        lg.error(f"Error in /insurance route: {e}")
        raise CustomException(e, sys)
    
@app.route('/multi_disease')
def multi_disease():
    return render_template("multi_disease.html")

@app.route('/disease_input_type')
def disease_input_type():
    return render_template("disease_input_type.html")




UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/disease_image_input', methods=['POST', 'GET'])
def disease_image_input():
    if request.method == 'POST':
        file = request.files['image']
        if file and allowed_file(file.filename):
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            img = file_path

            # model = ImagePrediction()
            # pred, class_name = model.predict(img)
            llm = report_generator()
            # response = llm.report(pred,class_name)
            

            # return render_template("disease_image_input.html", response = response)
        return render_template("disease_image_input.html")
    return render_template("disease_image_input.html")

@app.route('/food', methods=['GET', 'POST'])
def food():
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            file = file_path

        disease = request.form.get('disease')
        if disease == "":
            disease = None
        else:
            disease = disease.strip()  # Ensure it's a clean string

        # Create an instance of the class
        # generator = food_report_generator()
        
        # Call the report method
        # response = generator.report(file, disease)
        # return render_template('food-output.html', response=response)
    return render_template('food-input.html')



if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
    

