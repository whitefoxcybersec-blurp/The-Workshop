#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>

#define EPISODES 2000
#define INITIAL_BUDGET 10

// Estrutura do Ambiente Sintético
typedef struct {
    int state;
    double drift_level;
} Environment;

// Inicializa o ambiente
void env_reset(Environment *env) {
    env->state = rand() % 2;
}

// Emulação do Sensor com ruído induzido por drift
int env_observe(Environment *env, int sensor_id) {
    double noise = 0.1 + (env->drift_level * ((double)rand() / RAND_MAX) * 0.5);
    if (noise > 0.4) noise = 0.4;
    
    double acc_map[4] = {0.65 - noise, 0.75 - noise, 0.90 - noise, 0.85 - noise};
    double p_correct = acc_map[sensor_id];
    
    double roll = (double)rand() / RAND_MAX;
    if (roll < p_correct) {
        return env->state;
    } else {
        return 1 - env->state;
    }
}

// Lógica da Política Gulosa (Greedy Information Gain)
int select_action_greedy(double belief, int *costs, int budget_left) {
    int best_sensor = -1;
    double max_score = -1e9;
    double h_current = -belief * log2(belief + 1e-9) - (1 - belief) * log2(1 - belief + 1e-9);
    
    double acc_map[4] = {0.65, 0.75, 0.90, 0.85};
    
    for (int i = 0; i < 4; i++) {
        if (costs[i] > budget_left) continue;
        double score = (acc_map[i] * h_current) / ((double)costs[i] + 1e-5);
        if (score > max_score) {
            max_score = score;
            best_sensor = i;
        }
    }
    return best_sensor;
}

int main() {
    srand(time(NULL));
    int costs[4] = {1, 2, 5, 4};
    Environment env;
    env.drift_level = 0.2;
    
    long total_utility = 0;
    long total_cost_spent = 0;

    for (int ep = 0; ep < EPISODES; ep++) {
        env_reset(&env);
        double belief = 0.5;
        int budget = INITIAL_BUDGET;
        
        while (budget > 0) {
            int action = select_action_greedy(belief, costs, budget);
            if (action == -1) break;
            
            int cost = costs[action];
            budget -= cost;
            total_cost_spent += cost;
            
            int obs = env_observe(&env, action);
            
            // Atualização Bayesiana em C
            double acc_map[4] = {0.65, 0.75, 0.90, 0.85};
            double p_acc = acc_map[action];
            double lik_s1 = (obs == 1) ? p_acc : (1.0 - p_acc);
            double lik_s0 = (obs == 1) ? (1.0 - p_acc) : p_acc;
            
            double unnorm_s1 = lik_s1 * belief;
            double unnorm_s0 = lik_s0 * (1.0 - belief);
            double total = unnorm_s1 + unnorm_s0;
            
            if (total > 0) {
                belief = unnorm_s1 / total;
            }
        }
        
        int pred = (belief >= 0.5) ? 1 : 0;
        int utility = (pred == env.state) ? 1 : -2;
        total_utility += utility;
    }

    double efficiency = (double)total_utility / ((double)total_cost_spent + 1e-5);
    printf("Simulação em C Concluída\n");
    printf("Utilidade Acumulada: %ld\n", total_utility);
    printf("Custo Total Gasto: %ld\n", total_cost_spent);
    printf("Eficiência da Política (U/C): %.4f\n", efficiency);
    
    return 0;
}