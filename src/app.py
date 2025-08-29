import requests
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import time

# Configuración de la página de Streamlit
st.set_page_config(
    page_title="Vuelos Aerolíneas Argentinas - Córdoba",
    page_icon="✈️",
    layout="wide"
)

def get_time_range():
    """
    Siempre devuelve el rango de las próximas 24 horas
    """
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=24)
    return start_time, end_time

def get_flight_data_from_fr24(url, flight_type):
    """
    Obtiene datos de FlightRadar24 para llegadas o salidas
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.flightradar24.com/',
        'Origin': 'https://www.flightradar24.com'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            flights = data.get('result', {}).get('response', {}).get('airport', {}).get('pluginData', {}).get('schedule', {}).get(flight_type, {}).get('data', [])
            return flights
        else:
            return []
            
    except Exception as e:
        st.error(f"Error al obtener {flight_type}: {e}")
        return []

def process_flight_data(flights, flight_type, start_timestamp, end_timestamp):
    """
    Procesa los datos de vuelos y filtra por Aerolíneas Argentinas y rango horario
    """
    processed_data = []
    
    for flight in flights:
        try:
            # Información de la aerolínea
            airline = flight.get('flight', {}).get('airline', {})
            airline_code = airline.get('code', {}).get('iata', '')
            
            # Solo procesar vuelos de Aerolíneas Argentinas (AR)
            if airline_code != 'AR':
                continue
            
            # Número de vuelo
            flight_number_data = flight.get('flight', {}).get('identification', {}).get('number', {})
            flight_number = flight_number_data.get('default', '') or flight_number_data.get('number', '')
            
            # Remover "AR" duplicado si existe
            if flight_number.startswith('AR'):
                flight_number = flight_number[2:]
            
            # Matrícula
            registration = flight.get('flight', {}).get('aircraft', {}).get('registration', '')
            
            # Tiempos
            time_data = flight.get('flight', {}).get('time', {})
            scheduled_time = time_data.get('scheduled', {}).get(f"{'arrival' if flight_type == 'arrivals' else 'departure'}", 0)
            estimated_time = time_data.get('estimated', {}).get(f"{'arrival' if flight_type == 'arrivals' else 'departure'}", 0)
            
            flight_time = estimated_time if estimated_time else scheduled_time
            
            # Filtrar por rango de tiempo
            if not (start_timestamp <= flight_time <= end_timestamp):
                continue
            
            # Aeropuertos
            if flight_type == 'arrivals':
                origin = flight.get('flight', {}).get('airport', {}).get('origin', {}).get('code', {}).get('iata', '')
                destination = 'COR'
            else:
                origin = 'COR'
                destination = flight.get('flight', {}).get('airport', {}).get('destination', {}).get('code', {}).get('iata', '')
            
            # Convertir timestamp a formato HH:MM
            time_dt = datetime.fromtimestamp(flight_time) if flight_time else None
            time_str = time_dt.strftime('%H:%M') if time_dt else ''
            
            flight_info = {
                'tipo': 'Llegada' if flight_type == 'arrivals' else 'Salida',
                'numero_vuelo': f"AR{flight_number}",
                'hora': time_str,
                'aeropuerto': origin if flight_type == 'arrivals' else destination,
                'matricula': registration,
                'timestamp': flight_time
            }
            
            processed_data.append(flight_info)
            
        except Exception as e:
            continue
    
    return processed_data

def combine_arrivals_departures(arrivals, departures):
    """
    Combina llegadas y salidas por matrícula según las reglas especificadas
    """
    combined_data = []
    processed_matriculas = set()
    
    # Excepciones - vuelos que deben permanecer separados
    exception_vuelos = {'AR1550', 'AR1552', 'AR1551', 'AR1553'}
    
    # Primero procesar las excepciones
    for flight in arrivals + departures:
        if flight['numero_vuelo'] in exception_vuelos:
            if flight['tipo'] == 'Llegada':
                combined_data.append({
                    'llegada': flight['numero_vuelo'],
                    'salida': '',
                    'STA': flight['hora'],
                    'ETA': '',
                    'origen': flight['aeropuerto'],
                    'destino': '',
                    'matricula': flight['matricula']
                })
            else:
                combined_data.append({
                    'llegada': '',
                    'salida': flight['numero_vuelo'],
                    'STA': '',
                    'ETA': flight['hora'],
                    'origen': '',
                    'destino': flight['aeropuerto'],
                    'matricula': flight['matricula']
                })
            processed_matriculas.add(flight['matricula'])
    
    # Combinar llegadas y salidas normales por matrícula
    for arrival in arrivals:
        if arrival['matricula'] in processed_matriculas or arrival['numero_vuelo'] in exception_vuelos:
            continue
        
        # Buscar salida correspondiente
        matching_departure = None
        for departure in departures:
            if (departure['matricula'] == arrival['matricula'] and 
                departure['matricula'] not in processed_matriculas and
                departure['numero_vuelo'] not in exception_vuelos):
                matching_departure = departure
                break
        
        if matching_departure:
            combined_data.append({
                'llegada': arrival['numero_vuelo'],
                'salida': matching_departure['numero_vuelo'],
                'STA': arrival['hora'],
                'ETA': matching_departure['hora'],
                'origen': arrival['aeropuerto'],
                'destino': matching_departure['aeropuerto'],
                'matricula': arrival['matricula']
            })
            processed_matriculas.add(arrival['matricula'])
            processed_matriculas.add(matching_departure['matricula'])
        else:
            # Solo llegada
            combined_data.append({
                'llegada': arrival['numero_vuelo'],
                'salida': '',
                'STA': arrival['hora'],
                'ETA': '',
                'origen': arrival['aeropuerto'],
                'destino': '',
                'matricula': arrival['matricula']
            })
            processed_matriculas.add(arrival['matricula'])
    
    # Agregar salidas sin llegada correspondiente
    for departure in departures:
        if (departure['matricula'] not in processed_matriculas and 
            departure['numero_vuelo'] not in exception_vuelos):
            combined_data.append({
                'llegada': '',
                'salida': departure['numero_vuelo'],
                'STA': '',
                'ETA': departure['hora'],
                'origen': '',
                'destino': departure['aeropuerto'],
                'matricula': departure['matricula']
            })
            processed_matriculas.add(departure['matricula'])
    
    return combined_data

def main():
    """
    Función principal - Dashboard Streamlit
    """
    # Header de la aplicación
    st.title("✈️ Vuelos AR - COR")
    st.markdown("---")
    
    st.markdown("""
        <style>
        div.stButton > button:first-child {
            background: linear-gradient(45deg, #1E90FF, #00BFFF);
            color: white;
            border-radius: 12px;
            border: none;
            padding: 0.6em 1.2em;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease; /* animación suave */
        }
        div.stButton > button:first-child:hover {
            background: linear-gradient(45deg, #00BFFF, #1E90FF);
            transform: scale(1.05); /* efecto zoom */
        }
        </style>
    """, unsafe_allow_html=True)

    # Botón para actualizar datos
    if st.button("🔄 Actualizar Datos"):
        with st.spinner("Obteniendo datos de vuelos..."):
            # Obtener rango de tiempo automático (siempre 24 horas)
            start_time, end_time = get_time_range()
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            st.info(f"Buscando vuelos desde {start_time.strftime('%Y-%m-%d %H:%M')} hasta {end_time.strftime('%Y-%m-%d %H:%M')}")
            
            # URLs de FlightRadar24
            arrivals_url = "https://api.flightradar24.com/common/v1/airport.json?code=COR&plugin[]=schedule&plugin-setting[schedule][mode]=arrivals&page=1&limit=100"
            departures_url = "https://api.flightradar24.com/common/v1/airport.json?code=COR&plugin[]=schedule&plugin-setting[schedule][mode]=departures&page=1&limit=100"
            
            # Obtener y procesar llegadas
            arrivals_raw = get_flight_data_from_fr24(arrivals_url, 'arrivals')
            arrivals_processed = process_flight_data(arrivals_raw, 'arrivals', start_timestamp, end_timestamp)
            
            # Obtener y procesar salidas
            departures_raw = get_flight_data_from_fr24(departures_url, 'departures')
            departures_processed = process_flight_data(departures_raw, 'departures', start_timestamp, end_timestamp)
            
            if not arrivals_processed and not departures_processed:
                st.error("No se encontraron vuelos de Aerolíneas Argentinas en el rango de 24 horas")
                return
            
            # Combinar llegadas y salidas
            combined_data = combine_arrivals_departures(arrivals_processed, departures_processed)
            
            if not combined_data:
                st.error("No se pudieron combinar los datos")
                return
            
            # Crear DataFrame
            df = pd.DataFrame(combined_data)
            
            # Ordenar por hora
            if 'STA' in df.columns and 'ETA' in df.columns:
                df['orden_temporal'] = df['STA'].where(df['STA'] != '', df['ETA'])
                df = df.sort_values('orden_temporal')
                df = df.drop('orden_temporal', axis=1)
            
            # Columnas en el orden correcto
            column_order = ['llegada', 'salida', 'STA', 'ETA', 'origen', 'destino', 'matricula']
            df = df[column_order]
            
            # Reemplazar NaN y None con celdas vacías
            df = df.fillna('')
            
            # Mostrar estadísticas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Vuelos", len(df))
            with col2:
                st.metric("Llegadas", len([x for x in combined_data if x['llegada']]))
            with col3:
                st.metric("Salidas", len([x for x in combined_data if x['salida']]))
            
            # Mostrar tabla
            st.subheader("📊 Programación de Vuelos")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "llegada": "Llegada",
                    "salida": "Salida",
                    "STA": "STA",
                    "ETA": "ETA",
                    "origen": "Origen",
                    "destino": "Destino",
                    "matricula": "Matrícula"
                }
            )
            
            # Botón para descargar Excel
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar como CSV",
                data=csv,
                file_name="vuelos.csv",
                mime="text/csv"
            )
            
            st.success("Datos actualizados correctamente")

    else:
        st.info("Presiona el botón 'Actualizar Datos' para obtener la información de vuelos")

# Footer
st.markdown("---")
st.caption("Datos obtenidos de FlightRadar24 | Actualizado automáticamente cada vez que se presiona el botón")

if __name__ == "__main__":
    main()