from flask import Flask, request, render_template, jsonify
from getting_weather import get_weather_data
from weather_model import check_bad_weather
import socket
import requests
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
import plotly.graph_objects as go

app = Flask(__name__)


# GET /weather?start_lat=34.0522&start_lon=-118.2437&end_lat=40.7128&end_lon=-74.0060 из лос-анджелеса в нью йорк

dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dash/')


# Функция для создания графиков
def create_weather_graph(weather_data):
    # График температуры, скорости ветра и вероятности осадков
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=['Temperature (C)', 'Wind Speed (km/h)', 'Precipitation Probability (%)'],
        y=[weather_data["Temperature (C)"], weather_data["Wind Speed (km/h)"],
           weather_data["Precipitation Probability (%)"]],
        mode='lines+markers',
        name='Weather Data'
    ))

    fig.update_layout(
        title='Weather Data Visualization',
        xaxis_title='Weather Parameters',
        yaxis_title='Values',
        showlegend=True
    )

    return fig

# Обработчик GET-запроса для отображения html версии
@app.route('/', methods=['GET'])
def form():
    return render_template('html.html')


# Функция для проверки подключения к сети
def is_connected():
    try:
        # Пытаемся подключиться к одному из популярных сайтов
        socket.create_connection(("www.google.com", 80), timeout=5)
        return True
    except OSError:
        return False


# Функция для создания одного графика с несколькими параметрами
def create_combined_graph(start_weather, end_weather):
    # Создаем график с несколькими параметрами
    combined_graph = go.Figure()

    # Температура
    combined_graph.add_trace(go.Scatter(
        x=['Start Point', 'End Point'],
        y=[start_weather["Temperature (C)"], end_weather["Temperature (C)"]],
        mode='lines+markers',
        name='Temperature (°C)',
        line=dict(color='red')
    ))

    # Влажность
    combined_graph.add_trace(go.Scatter(
        x=['Start Point', 'End Point'],
        y=[start_weather["Humidity (%)"], end_weather["Humidity (%)"]],
        mode='lines+markers',
        name='Humidity (%)',
        line=dict(color='blue')
    ))

    # Скорость ветра
    combined_graph.add_trace(go.Scatter(
        x=['Start Point', 'End Point'],
        y=[start_weather["Wind Speed (km/h)"], end_weather["Wind Speed (km/h)"]],
        mode='lines+markers',
        name='Wind Speed (km/h)',
        line=dict(color='green')
    ))

    # Вероятность осадков
    combined_graph.add_trace(go.Scatter(
        x=['Start Point', 'End Point'],
        y=[start_weather["Precipitation Probability (%)"], end_weather["Precipitation Probability (%)"]],
        mode='lines+markers',
        name='Precipitation Probability (%)',
        line=dict(color='purple')
    ))

    # Настройка графика
    combined_graph.update_layout(
        title='Weather Parameters Comparison',
        xaxis_title='Points',
        yaxis_title='Value',
        legend=dict(title="Parameters", orientation="h", y=-0.2, x=0.5, xanchor="center"),
        template="plotly_white"
    )

    return combined_graph

# Обработчик POST-запроса для получения данных о погоде
@app.route('/weather', methods=['POST'])
def get_weather():
    try:
        # Получаем координаты из формы
        start_lat = request.form.get('start_lat')
        start_lon = request.form.get('start_lon')
        end_lat = request.form.get('end_lat')
        end_lon = request.form.get('end_lon')

        # Проверка на не заполненные ячейки
        if not (start_lat and start_lon and end_lat and end_lon):
            return render_template('error.html', message="Пожалуйста, заполните все поля :)")

        # Проверка корректности координат
        if not validate_coordinates(start_lat, start_lon, end_lat, end_lon):
            return render_template('error.html',
                                   message="Проверьте корректность координат и повторите попытку")

        if not is_connected():
            return render_template('error.html', message="Ошибка подключения: проверьте ваше интернет-соединение.")

        # Проверка на работоспособность API и подключение к сети
        try:
            start_weather = get_weather_data(start_lat, start_lon)
            end_weather = get_weather_data(end_lat, end_lon)
        except requests.ConnectionError:
            return render_template('error.html', message="Ошибка подключения: проверьте ваше интернет-соединение.")
        except requests.RequestException:
            return render_template('error.html', message="Ошибка подключения к API :(. Попробуйте позже.")

        # Проверяем на ошибки при получении погоды для начальной точки
        if "error" in start_weather:
            print(f"Ошибка при получении погоды для начальной точки: {start_weather['error']}")
            return render_template('error.html',
                                   message=f"Ошибка при получении данных о погоде для начальной точки, попробуйте ввести корректные координаты ещё раз")

        # Проверяем на ошибки при получении погоды для конечной точки
        if "error" in end_weather:
            print(f"Ошибка при получении погоды для конечной точки: {end_weather['error']}")
            return render_template('error.html',
                                   message=f"Ошибка при получении данных о погоде для конечной точки, попробуйте ввести корректные координаты ещё раз")

        # Оценка погодных условий для начальной точки
        start_weather_status = check_bad_weather(
            start_weather["Temperature (C)"],
            start_weather["Wind Speed (km/h)"],
            start_weather["Precipitation Probability (%)"],
            start_weather["Humidity (%)"]
        )

        # Оценка погодных условий для конечной точки
        end_weather_status = check_bad_weather(
            end_weather["Temperature (C)"],
            end_weather["Wind Speed (km/h)"],
            end_weather["Precipitation Probability (%)"],
            end_weather["Humidity (%)"]
        )

        result = {
            "start_point": {
                "coordinates": {"lat": start_lat, "lon": start_lon},
                "weather": start_weather,
                "status": start_weather_status
            },
            "end_point": {
                "coordinates": {"lat": end_lat, "lon": end_lon},
                "weather": end_weather,
                "status": end_weather_status
            }
        }

        # Создаем объединенный график
        combined_graph = create_combined_graph(start_weather, end_weather)

        # Рендерим HTML с результатами и графиком
        return render_template(
            'weather.html',
            result=result,
            combined_graph=combined_graph.to_html(full_html=False)
        )

    except Exception as e:
        return render_template(
            'error.html',
            message="Произошла неожиданная ошибка, проверьте подключение к сети и повторите попытку"
        )

# Создаем Dash приложение с графиками
dash_app.layout = html.Div([
    html.H1("Weather Data Visualization", style={'text-align': 'center'}),
    dcc.Graph(
        id='start-point-graph',
        figure=create_weather_graph({
            "Temperature (C)": 25,
            "Wind Speed (km/h)": 10,
            "Precipitation Probability (%)": 20
        })
    ),
    dcc.Graph(
        id='end-point-graph',
        figure=create_weather_graph({
            "Temperature (C)": 22,
            "Wind Speed (km/h)": 15,
            "Precipitation Probability (%)": 50
        })
    )
])



def validate_coordinates(start_lat, start_lon, end_lat, end_lon):
    """Проверка корректности координат."""
    try:
        start_lat = float(start_lat)
        start_lon = float(start_lon)
        end_lat = float(end_lat)
        end_lon = float(end_lon)

        if not (-90 <= start_lat <= 90 and -180 <= start_lon <= 180):
            return False
        if not (-90 <= end_lat <= 90 and -180 <= end_lon <= 180):
            return False
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    app.run(debug=True)
