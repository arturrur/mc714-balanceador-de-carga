import simpy
import random
import itertools

 
# Constantes de Entrada
CPU_TIME_AVG = 3
CPU_TIME_STD_DEV = 0.5
IO_TIME_AVG = 9
IO_TIME_STD_DEV = 1
AVERAGE_ARRIVAL_INTERVAL = 4
CPU_REQUEST_PERCENTAGE = 0.7

# Número de servidores
NUM_SERVERS = 3
# Duração da simulação
TOTAL_TIME_DURATION = 800
 

class Metrics:
    def __init__(self):
        self.response_times = []
        self.server_work_time = [0] * NUM_SERVERS
    
    def add_response_time(self, time):
        self.response_times.append(time)
    
    def add_server_work(self, server_id, time):
        self.server_work_time[server_id] += time

    
    def show_metrics(self):
        # Vazão
        print(f"Vazão do sistema: {len(self.response_times)/TOTAL_TIME_DURATION:.2f}")
        
        # Tempo médio de resposta
        print(f"Tempo médio de resposta: {sum(self.response_times)/len(self.response_times):.2f}")
        
        # Utilização do sistema
        print("----Informações de utilização----")
        sum_utilization = 0
        for id, work_time in enumerate(self.server_work_time):
            utilization = (work_time / TOTAL_TIME_DURATION) * 100
            sum_utilization += utilization
            print(f"Utilização do servidor {id}: {utilization:.2f}%")
        
        print(f"Utilização média do sistema: {(sum_utilization / NUM_SERVERS):.2f}%")
        




class Balancer:
    def __init__(self, env, servers, metrics, method="random"):
        self.env = env
        self.servers = servers
        self.metrics = metrics
        self.method = method
        
        # Usado para as métricas
        self.response_times = list()
        self.completed_requests = 0
        # Usado para Round Robin
        self.rr_counter = 0
        
        
    
    # decide o servidor responsável por atender a requisição
    def distribute(self, req):
        if self.method == "random":
            chosen_server = random.choice(self.servers)
        
        elif self.method == "shortest_queue":
            chosen_server = min(self.servers, key=lambda x: len(x.queue))
        
        elif self.method == "round_robin":
            chosen_server = self.servers[self.rr_counter]
            self.rr_counter = (self.rr_counter + 1) % NUM_SERVERS
        
        else:
            raise ValueError(f"Método de balanceamento desconhecido")
        
        server_id = self.servers.index(chosen_server)
        #print(f"{self.env.now:.2f}: Req {req['id']} enviada para Servidor {server_id}")
        self.env.process(process_request(self.env, req, chosen_server, server_id, self.metrics))


def process_request(env, req, server, server_id, metrics):
    with server.request() as request:
        # espera servidor ficar livre
        yield request
        
        # "processa" requisição
        yield env.timeout(req["duration"])
        
        # atualiza métricas
        metrics.add_response_time(env.now - req["arrival"])
        metrics.add_server_work(server_id, req["duration"])
        
    
def generate_requests(env, balancer):
    
    for i in itertools.count():
        if random.random() < CPU_REQUEST_PERCENTAGE:
            req_type = "CPU"
            # Gera um balor aleatório com média CPU_TIME_AVG e desvio padrão CPU_TIME_STD_DEV
            process_time = random.normalvariate(CPU_TIME_AVG, CPU_TIME_STD_DEV)
        else:
            req_type = "I/O"
            # Gera um balor aleatório com média IO_TIME_AVG e desvio padrão IO_TIME_STD_DEV
            process_time = random.normalvariate(IO_TIME_AVG, IO_TIME_STD_DEV)
        
        # Garantir que não é zero nem negativo
        process_time = max(0.1, process_time)
        
        # Cria requisição
        req = {
            "id": i,
            "type": req_type,
            "arrival": env.now,
            "duration": process_time,
        }
        
        # Envia requisição para o balancer
        balancer.distribute(req)
        
        #Espera um intervalo aleatório para criar nova requisição (distribuição exponencial com média AVERAGE_ARRIVAL_INTERVAL) 
        interval = random.expovariate(1.0 / AVERAGE_ARRIVAL_INTERVAL)
        yield env.timeout(interval)


if __name__ == "__main__":
    # Replicabilidade
    random.seed(7777)
        
    env = simpy.Environment()
    
    servers = []
    for _ in range(NUM_SERVERS):
        servers.append(simpy.Resource(env, 1))
        
    metrics = Metrics()
    balancer = Balancer(env, servers, metrics, "round_robin")
    
    env.process(generate_requests(env, balancer))
    
    env.run(until=TOTAL_TIME_DURATION)
    
    metrics.show_metrics()
    