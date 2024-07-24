import requests
import pytesseract
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from pdf2image import convert_from_path
import tempfile



def fetch_school_details(place_id, lng, lat):

    api_key = 'iW9ceziSt7BhDuG3FZGbuRkk09ETfoDJznAqwbcjMBw'
    url = f'https://discover.search.hereapi.com/v1/discover?at={lat},{lng}&q=schools&apiKey={api_key}'

    response = requests.get(url)
    data = response.json()

    for item in data['items']:
        if item['id'] == place_id:
            school_details = {
                'name': item['title'],
                'address': item['address']['label'],
                'latitude': item['position']['lat'],
                'longitude': item['position']['lng'],
                'distance': item.get('distance', None),
                'phone': item['contacts'][0]['phone'][0]['value'] if 'contacts' in item and 'phone' in item['contacts'][0] else None,
                'website': item['contacts'][0]['www'][0]['value'] if 'contacts' in item and 'www' in item['contacts'][0] else None,
                'email': item['contacts'][0]['email'][0]['value'] if 'contacts' in item and 'email' in item['contacts'][0] else None
            }

            return school_details

    return None



def ocr_from_image(file):
    # Determine if the file is an image or a PDF
    if file.content_type in ['image/jpeg', 'image/png']:
        image = Image.open(file)
        text = pytesseract.image_to_string(image)
    elif file.content_type == 'application/pdf':
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(file.read())
            temp.close()
            pages = convert_from_path(temp.name)
            text = ""
            for page in pages:
                text += pytesseract.image_to_string(page)
    else:
        raise TypeError('Unsupported file type')

    return text


def extract_details_from_text(text):
    data = {
        "parent_email": "",
        "parent_title": "",
        "parent_forename": "",
        "parent_surname": "",
        "parent_sex": "",
        "parent_address": "",
        "parent_phone": "",
        "child_name": "",
        "child_dob": "",
        "child_gender": "",
        "child_nhs": "",
        "preferences": []
    }

    lines = text.split('\n')
    for i, line in enumerate(lines):
        if "Email Address:" in line:
            data["parent_email"] = lines[i + 1].strip()
        elif "Title (Mr/Mrs):" in line:
            data["parent_title"] = lines[i + 1].strip()
        elif "Forename:" in line:
            data["parent_forename"] = lines[i + 1].strip()
        elif "Surname:" in line:
            data["parent_surname"] = lines[i + 1].strip()
        elif "Sex (Male/Female):" in line:
            data["parent_sex"] = lines[i + 1].strip()
        elif "Address:" in line:
            data["parent_address"] = lines[i + 1].strip()
        elif "Phone Number:" in line:
            data["parent_phone"] = lines[i + 1].strip()
        elif "Name:" in line:
            data["child_name"] = lines[i + 1].strip()
        elif "Date of Birth:" in line:
            data["child_dob"] = lines[i + 1].strip()
        elif "Gender:" in line:
            data["child_gender"] = lines[i + 1].strip()
        elif "NHS Number:" in line:
            data["child_nhs"] = lines[i + 1].strip()
        elif "Preference" in line:
            preference = {}
            while i < len(lines):
                i += 1
                next_line = lines[i].strip()
                if next_line.startswith("School"):
                    preference["school_name"] = next_line.split(":")[1].strip()
                elif next_line.startswith("Sibling Name"):
                    preference["sibling_name"] = next_line.split(":")[1].strip()
                elif next_line.startswith("Sibling Date of Birth"):
                    preference["sibling_dob"] = next_line.split(":")[1].strip()
                elif next_line.startswith("Sibling Year Group"):
                    preference["sibling_year_group"] = next_line.split(":")[1].strip()
                elif next_line == "":
                    break
            data["preferences"].append(preference)
    return data


def create_pdf_template(file_path):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 50, "School Admission Application Form")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 100, "Parent Details")
    c.setFont("Helvetica", 12)

    # Parent Details
    c.drawString(50, height - 120, "Email Address:")
    c.line(200, height - 122, 550, height - 122)
    c.drawString(50, height - 140, "Title (Mr/Mrs):")
    c.line(200, height - 142, 550, height - 142)
    c.drawString(50, height - 160, "Forename:")
    c.line(200, height - 162, 550, height - 162)
    c.drawString(50, height - 180, "Surname:")
    c.line(200, height - 182, 550, height - 182)
    c.drawString(50, height - 200, "Sex (Male/Female):")
    c.line(200, height - 202, 550, height - 202)
    c.drawString(50, height - 220, "Address:")
    c.line(200, height - 222, 550, height - 222)
    c.drawString(50, height - 240, "Phone Number:")
    c.line(200, height - 242, 550, height - 242)

    # Child Details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 280, "Child Details")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 300, "Name:")
    c.line(200, height - 302, 550, height - 302)
    c.drawString(50, height - 320, "Date of Birth:")
    c.line(200, height - 322, 550, height - 322)
    c.drawString(50, height - 340, "Gender:")
    c.line(200, height - 342, 550, height - 342)
    c.drawString(50, height - 360, "NHS Number:")
    c.line(200, height - 362, 550, height - 362)

    # School Preferences
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 400, "School Preferences")
    c.setFont("Helvetica", 12)
    for i in range(1, 4):
        y_offset = 420 + (i - 1) * 100  # Adjusted spacing to avoid overlap
        c.drawString(50, height - y_offset, f"Preference {i}")

        y_offset += 20
        c.drawString(50, height - y_offset, f"School {i} Name:")
        c.line(200, height - (y_offset + 2), 550, height - (y_offset + 2))

        y_offset += 20
        c.drawString(50, height - y_offset, f"Sibling {i} Name:")
        c.line(200, height - (y_offset + 2), 550, height - (y_offset + 2))

        y_offset += 20
        c.drawString(50, height - y_offset, f"Sibling {i} Date of Birth:")
        c.line(200, height - (y_offset + 2), 550, height - (y_offset + 2))

        y_offset += 20
        c.drawString(50, height - y_offset, f"Sibling {i} Year Group:")
        c.line(200, height - (y_offset + 2), 550, height - (y_offset + 2))

    c.save()

create_pdf_template("admission_form_template.pdf")




