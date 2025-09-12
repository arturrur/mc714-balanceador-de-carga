import simpy
import random
import itertools

 
# Constantes de Entrada
CPU_TIME_PROCESS = 3
CPU_TIME_STD_DEV = 0.5
IO_TIME_PROCESS = 9
IO_TIME_STD_DEV = 1
AVERAGE_ARRIVAL_INTERVAL = 4
CPU_REQUEST_PERCENTAGE = 0.7

# Número de servidores
NUM_SERVERS = 3
# Duração da simulação
TOTAL_TIME_DURATION = 800
 





class Balancer:
    def __init__(self, env, servers, method="random"):
        self.env = env
        self.servers = servers
        self.method = method
        self.rr_counter = 0 #Round robin counter
        
    
    # decide o servidor responsável por atender a requisição
    def distribute(self, req):
        if self.method == "random":
            chosen_server = random.choice(self.servers)
        
        elif self.method == "shortestQueue":
            chosen_server = min(self.servers, key=lambda x: len(x.queue))
        
        elif self.method == "roundRobin":
            chosen_server = self.servers[self.rr_counter]
            self.rr_counter = (self.rr_counter + 1) % NUM_SERVERS
        
        else:
            raise ValueError(f"Método de balanceamento desconhecido")
        
        server_id = self.servers.index(chosen_server)
        print(f"{self.env.now:.2f}: Req {req['id']} enviada para Servidor {server_id}")
        self.env.process(process_request(self.env, req, chosen_server, server_id))


def process_request(env, req, server, server_id):
    with server.request() as request:
        # espera servidor ficar livre
        yield request
        
        # "processa" requisição
        yield env.timeout(req["duration"])
        
        print(f"{env.now:.2f}: Servidor {server_id} TERMINA Req {req['id']}")
        
    # falta mensurar as métricas
    
def generate_requests(env, req, server):
    
    for i in itertools.count():
        if random.random() < CPU_REQUEST_PERCENTAGE:
            req_type = "CPU"
            avg_time = CPU_TIME_PROCESS
            actual_time = random.normalvariate(avg_time, CPU_TIME_STD_DEV)
        else:
            req_type = "I/O"
            avg_time = IO_TIME_PROCESS
            actual_time = random.normalvariate(avg_time, IO_TIME_STD_DEV)
        
        # Garantir que não é zero nem negativo
        actual_time = max(0.1, actual_time)
        
        # Cria requisição
        req = {
            "id": i,
            "type": req_type,
            "arrival": env.now,
            "duration": actual_time,
        }
        
        # Envia requisição para o balancer
        balancer.distribute(req)
        
        #Espera para criar a proxima requisição
        interval = random.expovariate(1.0 / AVERAGE_ARRIVAL_INTERVAL)
        yield env.timeout(interval)


if __name__ == "__main__":
    # Replicabilidade
    random.seed(7777)
        
    env = simpy.Environment()
    
    servers = []
    for _ in range(NUM_SERVERS):
        servers.append(simpy.Resource(env, 1))
        
    
    balancer = Balancer(env, servers, "random")
    
    env.process(generate_requests(env, servers, balancer))
    
    env.run(until=TOTAL_TIME_DURATION)