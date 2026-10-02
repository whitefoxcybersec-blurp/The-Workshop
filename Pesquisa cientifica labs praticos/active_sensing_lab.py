import csv
from pathlib import Path

import numpy as np

class SyntheticEnvironment:
    """Camada 01: Ambiente com estado oculto S e 4 sensores com custos e perfis informacionais."""
    def __init__(self, drift_level=0.0):
        self.state = 0
        self.drift = drift_level
        
    def reset(self):
        # S in {0, 1} com probabilidade a priori igual
        self.state = np.random.choice([0, 1])
        return self.state

    def observe(self, sensor_id):
        """
        Camada 02: Sensores A1, A2, A3, A4 com diferentes acurácias, custos e perfis.
        A1: Barato, baixa info.
        A2: Custo médio, info intermediária.
        A3: Alto custo, alta complementaridade/redundância.
        A4: Custo alto, perfil alternativo.
        """
        s = self.state
        # Introduz drift estocástico modificando a probabilidade de emissão P(Y|S)
        noise = np.clip(0.1 + self.drift * np.random.uniform(0, 0.5), 0.0, 0.4)
        
        if sensor_id == 0:  # A1 (Custo 1)
            p_correct = 0.65 - noise
        elif sensor_id == 1:  # A2 (Custo 2)
            p_correct = 0.75 - noise
        elif sensor_id == 2:  # A3 (Custo 5)
            p_correct = 0.90 - noise
        elif sensor_id == 3:  # A4 (Custo 4)
            p_correct = 0.85 - noise
        else:
            raise ValueError("Sensor inválido")

        # Retorna a evidência Y binária baseada na acurácia do sensor
        if np.random.rand() < p_correct:
            return s
        else:
            return 1 - s


class TabularReplayEnvironment:
    """Camada 02: replay temporal de uma tabela, uma linha por evento."""
    def __init__(self, data_path, sensor_columns=None, state_column="state"):
        self.data_path = Path(data_path)
        self.sensor_columns = sensor_columns or ["A1", "A2", "A3", "A4"]
        self.state_column = state_column
        self.rows = self._load_rows()
        self.row_index = -1
        self.current_row = None

    def _load_rows(self):
        with self.data_path.open(newline="", encoding="utf-8") as data_file:
            rows = list(csv.DictReader(data_file))
        missing = [column for column in self.sensor_columns if column not in rows[0]] if rows else self.sensor_columns
        if missing:
            raise ValueError(f"Colunas de sensores ausentes: {missing}")
        return rows

    def reset(self):
        if not self.rows:
            raise ValueError("O replay tabular não contém eventos")
        self.row_index = (self.row_index + 1) % len(self.rows)
        self.current_row = self.rows[self.row_index]
        state = self.current_row.get(self.state_column)
        return int(state) if state not in (None, "") else None

    def observe(self, sensor_id):
        if self.current_row is None:
            raise RuntimeError("Chame reset() antes de observe()")
        try:
            value = self.current_row[self.sensor_columns[sensor_id]]
        except (IndexError, KeyError) as error:
            raise ValueError("Sensor inválido ou coluna ausente") from error
        return int(float(value))

class AdaptiveAgent:
    """Camada 03 e 04: Agente que mantém crença, avalia VOI/custo e toma ações."""
    def __init__(self, sensor_costs):
        self.costs = sensor_costs
        self.belief = 0.5
        self._remaining_sensors = []
        
    def reset(self):
        self.belief = 0.5
        self._remaining_sensors = list(range(len(self.costs)))

    def update_belief(self, sensor_id, observation):
        # Atualização Bayesiana simples para estado binário
        # (Matriz de confusão simulada para Likelihood P(Y|S))
        acc_map = {0: 0.65, 1: 0.75, 2: 0.90, 3: 0.85}
        p_acc = acc_map[sensor_id]
        
        if observation == 1:
            likelihood_s1 = p_acc
            likelihood_s0 = 1 - p_acc
        else:
            likelihood_s1 = 1 - p_acc
            likelihood_s0 = p_acc
            
        # Bayes update
        unnormalized_s1 = likelihood_s1 * self.belief
        unnormalized_s0 = likelihood_s0 * (1 - self.belief)
        total = unnormalized_s1 + unnormalized_s0
        
        if total > 0:
            self.belief = unnormalized_s1 / total

    def select_action_greedy_voi(self, budget_left):
        """
        Baseline 4 / VOI Simplificado: Escolhe o sensor que maximiza 
        a redução de entropia esperada por unidade de custo.
        """
        best_sensor = -1
        max_score = -float('inf')
        
        # Entropia atual da crença
        h_current = -self.belief * np.log2(self.belief + 1e-9) - (1 - self.belief) * np.log2(1 - self.belief + 1e-9)

        for s_id, cost in enumerate(self.costs):
            if cost > budget_left:
                continue
            
            # Heurística de ganho de informação baseada na incerteza atual e acurácia do sensor
            acc_map = {0: 0.65, 1: 0.75, 2: 0.90, 3: 0.85}
            expected_reduction = acc_map[s_id] * h_current
            score = expected_reduction / (cost + 1e-5)
            
            if score > max_score:
                max_score = score
                best_sensor = s_id
                
        return best_sensor

    def select_action_fixed_a1(self, budget_left):
        """Baseline 1: consulta somente A1 enquanto houver orçamento."""
        return 0 if budget_left >= self.costs[0] else -1

    def select_action_all_sensors(self):
        """Baseline 2: consulta cada sensor uma vez, ignorando o custo."""
        if not self._remaining_sensors:
            return -1
        return self._remaining_sensors.pop(0)

    def select_action_random(self, budget_left):
        """Baseline 3: escolhe uniformemente entre sensores permitidos."""
        available = [sensor_id for sensor_id, cost in enumerate(self.costs) if cost <= budget_left]
        return int(np.random.choice(available)) if available else -1

    def select_action(self, policy, budget_left):
        policies = {
            "fixed_a1": self.select_action_fixed_a1,
            "random": self.select_action_random,
            "greedy_voi": self.select_action_greedy_voi,
        }
        if policy == "all_sensors":
            return self.select_action_all_sensors()
        try:
            return policies[policy](budget_left)
        except KeyError as error:
            raise ValueError(f"Política inválida: {policy}") from error

# Execução de um Episódio de Teste
def run_simulation(episodes=1000, initial_budget=10, policy="greedy_voi", env=None):
    costs = [1, 2, 5, 4]  # Custos de A1, A2, A3, A4
    env = env or SyntheticEnvironment(drift_level=0.2)
    agent = AdaptiveAgent(sensor_costs=costs)
    
    total_utility = 0
    total_cost_spent = 0
    
    for _ in range(episodes):
        true_state = env.reset()
        agent.reset()
        budget = initial_budget
        
        while budget > 0 or policy == "all_sensors":
            action = agent.select_action(policy, budget)
            if action == -1:
                break # Sem orçamento suficiente para mais nada
                
            cost = costs[action]
            if policy != "all_sensors":
                budget -= cost
            total_cost_spent += cost
            
            observation = env.observe(action)
            agent.update_belief(action, observation)
            
        # Decisão final com base na crença acumulada
        final_prediction = 1 if agent.belief >= 0.5 else 0
        if true_state is not None:
            utility = 1 if final_prediction == true_state else -2
            total_utility += utility

    efficiency = total_utility / (total_cost_spent + 1e-5)
    print(f"Simulação Concluída | Política: {policy} | Utilidade Acumulada: {total_utility}")
    print(f"Custo Total Gasto: {total_cost_spent} | Eficiência da Política (U/C): {efficiency:.4f}")
    return total_utility, total_cost_spent

if __name__ == "__main__":
    run_simulation()