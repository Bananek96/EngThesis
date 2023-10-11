from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/pl', methods=['GET'])
def index_pl():
    return render_template('index_pl.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
