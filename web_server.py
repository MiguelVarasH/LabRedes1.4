from os.path import exists, getsize
import mimetypes
import signal, datetime, select, socket, sys, queue, ssl

# variables globales
MAX_BUFFER = 1024
MAX_BACKLOG = 4
SERVER = socket.socket(socket.AF_INET, socket.SOCK_STREAM, proto=0)
SERVER_ADDRESS = socket.gethostbyname(socket.gethostname())
SERVER_NAME = socket.gethostname()
TIMEOUT = 10
PORT = 8080
#SERVERHTPPS = socket.socket(socket.AF_INET, socket.SOCK_STREAM, proto=0)
#SERVER_ADDRESS1 = socket.gethostbyname(socket.gethostname())
#PORT1 = 5050
HTTP_VERSIONS = ['HTTP/0.9','HTTP/1.0', 'HTTP/1.1']
SERVER_NAME = 'Alberto y Miguel'
SERVER_VERSION = '1.0'
CONTENT_TYPES = {
  'text': 'text/html; charset=UTF-8',
  'json': 'application/json'
}
RESPONSE_STATUS = {
  '200': 'Ok',
  '201': 'Created',
  '202': 'Accepted',
  '203': 'Non-Authoritative Information',
  '204': 'No Content',
  '205': 'Reset Content',
  '206': 'Partial Content',
  '207': 'Multi-Status',
  '208': 'Multi-Status',
  '226': 'IM Used',
  '300': 'Multiple Choice',
  '301': 'Moved Permanently',
  '302': 'Found',
  '303': 'See Other',
  '304': 'Not modified',
  '305': 'Use Proxy',
  '307': 'Temporary redirect',
  '308': 'Permanent Redirect',
  '400': 'Bad Request',
  '401': 'Unauthorized',
  '402': 'Payment Required',
  '403': 'Forbidden',
  '404': 'Not Found',
  '405': 'Method Not Allowed',
  '406': 'Not Acceptable',
  '407': 'Proxy Authentication Required',
  '408': 'Request Timeout',
  '409': 'Conflict',
  '410': 'Gone',
  '411': 'Length Required',
  '412': 'Precondition Failed',
  '413': 'Payload Too Large',
  '414': 'URI Too Long',
  '415': 'Unsupported Media Type',
  '416': 'Requested Range Not Satisfiable',
  '417': 'Expectation Failed',
  '418': 'I\'m a teapot',
  '421': 'Misdirected Request',
  '422': 'Unprocessable Entity',
  '423': 'Locked',
  '424': 'Failed Dependency',
  '426': 'Upgrade Required',
  '428': 'Precondition Required',
  '429': 'Too Many Requests',
  '431': 'Request Header Fields Too Large',
  '451': 'Unavailable For Legal Reasons',
  '500': 'Internal Server Error',
  '501': 'Not Implemented',
  '502': 'Bad Gateway',
  '503': 'Service Unavailable',
  '504': 'Gateway Timeout',
  '505': 'HTTP Version Not Supported',
  '506': 'Variant Also Negotiates',
  '507': 'Insufficient Storage',
  '508': 'Loop Detected',
  '510': 'Not Extended',
  '511': 'Network Authentication Required'
}
inputs = [SERVER]
outputs = []
message_queues = {}

#context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
#context.load_cert_chain('/home/administrador/Escritorio/P1_Lab_redes/P1.3/cert.pem')

def main():
  global PORT
  signal.signal(signal.SIGINT, signal_handler)
  if not validate_arguments():
    return -1
  PORT = int(sys.argv[1])
  config_server(SERVER_ADDRESS, PORT)
 # config_server_https(SERVER_ADDRESS1, PORT1)
  run_server(SERVER)

def run_server(server):
  print('Iniciando servidor...')
  server.listen(MAX_BACKLOG)
  print('Servidor iniciado!')
  print(f'------ {SERVER_NAME} - {SERVER_ADDRESS} ------')
  print(f'Servidor web escuchando peticiones en el puerto: {PORT}')
  while inputs:
    try:
      r_list, w_list, x_list = select.select(
          inputs, outputs, inputs, TIMEOUT)
      if not (r_list or w_list or x_list):
        raise TimeoutError
      handle_readable(r_list)
      handle_writable(w_list)
      handle_exceptional(x_list)
    except ValueError:
      print('ValueError catched')
      break
    except TimeoutError:
      print('Servidor web inactivo')
      continue
  server.close()
  return 1


# función para manejar la lista de sockets de lectura
def handle_readable(readable):
  for s in readable:
    if s is SERVER:
      connection, client_address = s.accept()
  #    connection=ssl.wrap_socket(connection,server_side=True,certfile="cert.pem",keyfile="key.pem",ssl_version=ssl.PROTOCOL_SSLv23)
#	with context.wrap_socket(s, server_side=True) as ssock:
#        conn, addr = ssock.accept()       
      print(f'Conexión entrante desde: {client_address}')
      connection.setblocking(0)
      inputs.append(connection)
      message_queues[connection] = queue.Queue()
    else:
      data = read_message(s)
      if not data:
        if s in outputs:
          outputs.remove(s)
        inputs.remove(s)
        s.close()
        del message_queues[s]
      else:
        handle_data(data, s)

# función para manejar la lista de sockets de escritura
def handle_writable(writable):
  for s in writable:
    try:
      msg = message_queues[s].get_nowait()
    except queue.Empty:
      outputs.remove(s)
    except KeyError:
      outputs.remove(s)
      del message_queues[s]
    else:
      manage_response(msg, s)


# función para manejar los sockets con excepción
def handle_exceptional(exceptional):
  for s in exceptional:
      inputs.remove(s)
      if s in outputs:
          outputs.remove(s)
      s.close()
      del message_queues[s]


# función para procesar respuesta a la solicitud de un socket
def manage_response(data, sock):
  headers = get_request_headers(data)
  if not is_http_request(headers[0]):
    res_headers = get_response_headers('400')
    print('Solicitud no es HTTP')
    handle_request_errors(sock, res_headers, './bad_request.html')
  else:
    if headers[0].split(' ')[0] == 'GET':
      print('Petición tipo GET recibida')
      handle_get(sock, headers)
    elif headers[0].split(' ')[0] == 'POST':
      post_data = data.decode().split('\r\n\r\n')[1]
      print(post_data)
      print('Petición tipo POST recibida')
      handle_post(sock, headers, post_data)
    else:
      http_version = headers[0].split(' ')[2]
      res_headers = get_response_headers('405', http_version)
      print('Método HTTP no admitido')
      handle_request_errors(sock, res_headers, './bad_request.html')

# función para respuestas de error
def handle_request_errors(sock, res_headers, template):
  content_length = getsize(template)
  mime, _ = mimetypes.guess_type(template)
  res_headers.insert(len(res_headers) - 2,f'Content-Length: {content_length}')
  res_headers.insert(len(res_headers) - 2,f'Content-Type: {mime}')
  send_response(sock, res_headers, template)

def get_header(headers, name):
  for header in headers:
    if name in header:
      return header
  return None


# función para manejar solicitudes de tipo POST
def handle_post(sock, headers, data):
  status = '201'
  http_version = headers[0].split(' ')[2]
  content_type = get_header(headers, 'Content-Type')
  if content_type:
    mime = content_type.split(': ')[1]
  else:
    mime = 'application/json'
  if not data:
    data = '{"error": "no se recibieron datos"}'
    status = '400'
  content_length = len(data.encode())
  res_headers = get_response_headers(status, http_version)
  res_headers.insert(len(res_headers) - 2,f'Content-Length: {content_length}')
  res_headers.insert(len(res_headers) - 2,f'Content-Type: {mime}')
  send_response(sock, res_headers, data, json_response=True)

# función para manejar solicitudes GET
def handle_get(sock, headers):
  resource = headers[0].split(' ')[1]
  http_version = headers[0].split(' ')[2]
  status = '200'
  if resource == '/':
    requested_resource = './index.html'
  else:
    requested_resource = '.' + resource
  if not exists(requested_resource):
    requested_resource = './not_found.html'
    status = '400'
  content_length = getsize(requested_resource)
  mime, _ = mimetypes.guess_type(requested_resource)
  res_headers = get_response_headers(status, http_version)
  res_headers.insert(len(res_headers) - 2,f'Content-Length: {content_length}')
  res_headers.insert(len(res_headers) - 2,f'Content-Type: {mime}')
  send_response(sock, res_headers, requested_resource)


# función para determinar si la solicitud es http
def is_http_request(header):
  informed_version = header.split(' ')[2]
  if not informed_version:
    return False
  return informed_version in HTTP_VERSIONS

# función de envío de respuesta
def send_response(sock, headers, resource, json_response=False):
  http_version = headers[0].split(' ')[0]
  if not json_response:
    try:
      file = open(resource, 'rb')
      body = file.read()
      file.close()
    except Exception as e:
      print(f'Excepción al leer el recurso: {e}')
      status = '500'
      headers[0] = f'{http_version} {status} {RESPONSE_STATUS.get(status)}'
  else:
    body = resource.encode()
  response = '\n'.join(headers).encode()
  if body:
    response += body
  sock.send(response)

def get_response_headers(status, http_version='HTTP/1.1'):
  headers = []
  status = f'{status} {RESPONSE_STATUS.get(status)}'
  headers.append(f'{http_version} {status}')
  headers.append(create_date_header(datetime.datetime.utcnow()))
  headers.append(f'Server: {SERVER_NAME}/{SERVER_VERSION} python/3.x')
  headers.append('Content-Language: es-ES')
  headers.append('Connection: close' if http_version != 'HTTP/1.1' else 'Connection: keep-alive')
  headers.append('\n')
  return headers

# función para obtener las cabeceras de la solicitud
def get_request_headers(request):
  decoded = request.decode().splitlines()
  headers = decoded[0:decoded.index('')]
  print(headers)
  return headers

def create_date_header(utc_dt):
  str_format = '%A, %d %b %Y %H:%M:%S GMT'
  return f'Date: {utc_dt.strftime(str_format)}'

# función para manejar los datos leidos del socket
def handle_data(data, sock):
  message_queues[sock].put(data)
  if sock not in outputs:
    outputs.append(sock)
  

# función para leer todos los datos enviados por el socket
def read_message(sock):
  chunks = []
  while True:
    try:
      data = sock.recv(MAX_BUFFER)
      if not data:
        return None
      chunks.append(data)
    except BlockingIOError:
      break
  return b"".join(chunks)

# función que configura el servidor de socket
def config_server(addr, port):
  print('Configurando servidor ...')
  SERVER.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  SERVER.setblocking(0)
  SERVER.bind((addr, port))
  print('Servidor configurado!')

#def config_server_https(addr, port):
#  print('Configurando servidor ...')
#  SERVERHTPPS.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#  SERVERHTPPS.setblocking(0)
#  SERVERHTPPS.bind((addr, port))
#  print('Servidor configurado!')

# función para validar los argumentos de entrada
def validate_arguments():
  use_msg = 'Uso:\n python ./servidor.py <puerto>'
  if(len(sys.argv) < 2):
    print('Número de puerto es necesario')
    print(use_msg)
    return False
  try:
    p = int(sys.argv[1])
  except ValueError:
    print(f'El valor del puerto introducido: "{sys.argv[1]}" no válido, debe ser numérico')
    print(use_msg)
    return False
  if p not in range(1024, 65536):
    print(f'El valor de puerto {p} debe encontrarse entre 1024 y 65535')
    print(use_msg)
    return False
  return True

# función para manejar la interrupción ctrl+c
def signal_handler(sig, frame):
  print('\nAdiós')
  SERVER.close()
  sys.exit(0)


if __name__ == "__main__":
  sys.exit(main())
