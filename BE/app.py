from flask import Flask
import numpy as np
from flask import jsonify
from flask import request
from flask_cors import CORS
import torch
import base64
from PIL import Image
import io
import torch
import os
import torchvision.transforms as transforms
from model import *

app = Flask(__name__)
app.debug = True
CORS(app)

GEN_FOLDER = 'model/gennew.pth.tar'

model = Generator(in_channels=3)
checkpoint = torch.load(GEN_FOLDER,map_location=torch.device('cpu'))
model.load_state_dict(checkpoint["state_dict"])
model.eval()

def base64_to_tensor(base64_string):
   
    base64_string = base64_string.replace("data:image/png;base64,", "")
    image_data = base64.b64decode(base64_string)

    image = Image.open(io.BytesIO(image_data))

    transform = transforms.Compose([
        transforms.ToTensor(),
    ])
    tensor = transform(image)

    return tensor.unsqueeze(0)

def tensor_to_base64(tensor):

    tensor = tensor.squeeze().detach()
    tensor = tensor.mul(255).clamp(0, 255).byte()
    image = transforms.ToPILImage()(tensor)

    buffer = io.BytesIO()
    image.save(buffer, format='JPEG')
    image_data = buffer.getvalue()

    base64_string = base64.b64encode(image_data).decode('utf-8')

    return base64_string

@app.route("/predict", methods=["POST"])
def predict():
    base64 = request.json.get("image", None)
    image = base64_to_tensor(base64)
    predict = model(image)
    res = {
        "image": str(tensor_to_base64(predict))
    }
    return jsonify(res)

