import simpy
import random
import itertools

# Número de servidores
NUM_SERVERS = 3
SERVER_SPEEDS = [1.5, 1, 0.5, 1] #0, 1, 2 são normais, 3 é emergencial
MAX_SIZE_QUEUE = 10


# Nota: μ vale 4 -> 0.5+1+1.5 + 1(emergencial)
# Nota: μ está sendo medido em poder de processamento por unidade de tempo

# Constantes de Entrada, 
CPU_TIME_AVG = 3
IO_TIME_AVG = 9
CPU_REQUEST_PERCENTAGE = 0.7

# Parâmetros dos experimentos
LAMBDAS = [2, 3, 4] # lambda das requisição (input)
METHODS = ["random", "round_robin", "shortest_queue", "least_work"] # Métodos testados no load balancer
TOTAL_TIME_DURATION = 10000
# Nota: λ = (CPU_TIME*CPU_PERCENTAGE + IO_TIME*IO_PERCENTAGE) * 1/AVERAGE_ARRIVAL_INTERVAL ->
# -> λ = 4.8/AVERAGE_ARRIVAL_INTERVAL

# Duração da simulação



class Metrics:
    def __init__(self):
        self.response_times = []
        self.server_work_time = [0] * (NUM_SERVERS + 1) # + 1 é o emergencial
        self.discarded_requests = 0

    def add_response_time(self, time):
        self.response_times.append(time)

    def add_server_work(self, server_id, time):
        self.server_work_time[server_id] += time
    
    def add_discarded_request(self):
        self.discarded_requests += 1

    def show_metrics(self):
        # Vazão
        print(f"Vazao do sistema: {len(self.response_times)/TOTAL_TIME_DURATION:.2f}")

        # Tempo médio de resposta
        print(
            f"Tempo medio de resposta: {sum(self.response_times)/len(self.response_times):.2f}"
        )

        # Utilização do sistema
        print("----Informacoes de utilizacao----")
        sum_utilization = 0
        for id, work_time in enumerate(self.server_work_time):
            utilization = (work_time / TOTAL_TIME_DURATION) * 100
            sum_utilization += utilization
            if id < NUM_SERVERS:
                print(f"Utilizacao do servidor {id}: {utilization:.2f}%")
            else:
                print(f"Utilizacao do servidor EMERGENCIAL: {utilization:.2f}%")

        print(f"Utilizacao media do sistema (considerando o emergencial): {(sum_utilization / (NUM_SERVERS + 1)):.2f}%")
        
        # Descarte de requisições
        print("----Informacoes de descarte----")
        if self.discarded_requests > 0:
            print(f"Requisições Processadas: {len(self.response_times)}")
            print(f"Requisições Descartadas: {self.discarded_requests} ({(self.discarded_requests / (self.discarded_requests + len(self.response_times))) * 100:.2f}%)")
        else:
            print(f"Requisições Processadas: {len(self.response_times)}")
            print(f"Requisições Descartadas: 0")


class Balancer:
    def __init__(self, env, servers, emergency_server, metrics, method="random"):
        self.env = env
        self.servers = servers
        self.emergency_server = emergency_server
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

        # política que faz uso do fato dos servidores terem processamentos diferentes
        elif self.method == "least_work":
            min_finish_time = float('inf')
            for i, server in enumerate(self.servers):
                speed = SERVER_SPEEDS[i]
                # tempo do que está sendo processado no momento
                current_workload = server.users[0].req['duration'] if server.users else 0
                # tempo de todos na fila
                queue_workload = sum(r.req['duration'] for r in server.queue if hasattr(r, "req"))
                
                expected_time = (current_workload + queue_workload) / speed
                
                if expected_time < min_finish_time:
                    min_finish_time = expected_time
                    chosen_server = server
            
        else:
            raise ValueError(f"Metodo de balanceamento desconhecido")

        server_id = self.servers.index(chosen_server)
        
        # Checar se a fila do servidor escolhido está cheia
        if len(self.servers[server_id].queue) >= MAX_SIZE_QUEUE:
            # Corrige chosen_server e server_id
            chosen_server = self.emergency_server  
            server_id = NUM_SERVERS
            
            # Se servidor emergencial também estiver cheio, descarta requisição
            if len(self.emergency_server.queue) >= MAX_SIZE_QUEUE:
                self.metrics.add_discarded_request()
                return # Encerra o método, requisição não é processada
            
        self.env.process(
            process_request(self.env, req, chosen_server, server_id, self.metrics)
        )


def process_request(env, req, server, server_id, metrics):
    with server.request() as request:
        # usado para a política least_work ter acesso aos tempos
        request.req = req
        
        # espera servidor ficar livre
        yield request

        server_spped = SERVER_SPEEDS[server_id]
        
        process_time = req["duration"] / server_spped
        
        # processa requisição na velocidade do servidor
        yield env.timeout(process_time)

        # atualiza métricas
        metrics.add_response_time(env.now - req["arrival"])
        metrics.add_server_work(server_id, process_time)


def generate_requests(env, balancer):

    for i in itertools.count():
        if random.random() < CPU_REQUEST_PERCENTAGE:
            req_type = "CPU"
            # Gera um valor aleatório com média CPU_TIME_AVG usando distribuição exponencial
            process_time = random.expovariate(1.0 / CPU_TIME_AVG)
        else:
            req_type = "I/O"
            # Gera um valor aleatório com média IO_TIME_AVG usando distribuição exponencial
            process_time = random.expovariate(1.0 / IO_TIME_AVG)

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

        # Espera um intervalo aleatório para criar nova requisição (distribuição exponencial com média AVERAGE_ARRIVAL_INTERVAL)
        interval = random.expovariate(1.0 / AVERAGE_ARRIVAL_INTERVAL)
        yield env.timeout(interval)
        
def run_experiment(method, lambd):
    '''
    Executa uma simulação completa para uma combinação de método e lambda.
    '''
    global AVERAGE_ARRIVAL_INTERVAL

    AVERAGE_ARRIVAL_INTERVAL = 4.8 / lambd
    
    print(f"\n--- Executando: Método = {method.upper()}, λ = {lambd}, μ = {sum(SERVER_SPEEDS)} ---")
    
    # cria ambiente da rodada atual (dupla método-lambda)
    env = simpy.Environment()

    # criar os três servidores padrões
    servers = []
    for _ in range(NUM_SERVERS):
        servers.append(simpy.Resource(env, 1))
    
    # cria servidor emergencial
    emergency_server = simpy.Resource(env, 1)

    metrics = Metrics()
    balancer = Balancer(env, servers, emergency_server, metrics, method)
    

    env.process(generate_requests(env, balancer))

    env.run(until=TOTAL_TIME_DURATION)

    metrics.show_metrics()


if __name__ == "__main__":
    # Replicabilidade
    random.seed(777)
    
    for lambd in LAMBDAS:
        for method in METHODS:
            run_experiment(method, lambd)
            
    
