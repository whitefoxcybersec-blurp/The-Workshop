#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>

#ifdef _OPENMP
#include <omp.h>
#endif

#define SENSOR_COUNT 4
#define STATE_COUNT 2
#define BELIEF_GRID 101
#define EPISODES 4000
#define INITIAL_BUDGET 10
#define HORIZON 3
#define SAMPLE_CAP 4096

// Declaração da função externa escrita em x64 Assembly.
// Assinatura: void update_belief_asm(double *belief, int sensor_id, int observation, double *acc_map);
extern void update_belief_asm(double *belief, int sensor_id, int observation, double *acc_map);

typedef struct {
    int state;
    int regime;
    double drift_level;
    double regime_transition[STATE_COUNT][STATE_COUNT];
} Environment;

typedef struct {
    double p[STATE_COUNT];
} Distribution;

static inline double clamp(double value, double lo, double hi) {
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

static inline double entropy_binary(double belief) {
    if (belief <= 0.0 || belief >= 1.0) return 0.0;
    return -(belief * log2(belief + 1e-9) + (1.0 - belief) * log2(1.0 - belief + 1e-9));
}

static inline int nearest_belief_index(double belief) {
    int index = (int)lround(belief * (BELIEF_GRID - 1));
    if (index < 0) return 0;
    if (index >= BELIEF_GRID) return BELIEF_GRID - 1;
    return index;
}

void env_reset(Environment *env) {
    env->state = rand() % STATE_COUNT;
    env->regime = rand() % STATE_COUNT;
    env->drift_level = (env->regime == 0) ? 0.12 : 0.28;

    if (env->regime == 0) {
        env->regime_transition[0][0] = 0.92;
        env->regime_transition[0][1] = 0.08;
        env->regime_transition[1][0] = 0.18;
        env->regime_transition[1][1] = 0.82;
    } else {
        env->regime_transition[0][0] = 0.72;
        env->regime_transition[0][1] = 0.28;
        env->regime_transition[1][0] = 0.34;
        env->regime_transition[1][1] = 0.66;
    }
}

void switch_regime(Environment *env) {
    double roll = (double)rand() / RAND_MAX;
    int next_regime = env->regime;

    if (roll < env->regime_transition[env->regime][0]) {
        next_regime = 0;
    } else {
        next_regime = 1;
    }

    env->regime = next_regime;
    env->drift_level = (env->regime == 0) ? 0.12 : 0.28;
}

int env_observe(Environment *env, int sensor_id, const double *acc_map) {
    double noise = 0.10 + env->drift_level * ((double)rand() / RAND_MAX) * 0.5;
    noise = clamp(noise, 0.0, 0.40);

    double p_correct = acc_map[sensor_id] - noise;
    p_correct = clamp(p_correct, 0.05, 0.99);

    double roll = (double)rand() / RAND_MAX;
    return (roll < p_correct) ? env->state : (1 - env->state);
}

void bayes_update(double *belief, int sensor_id, int observation, const double *acc_map) {
    double p_acc = acc_map[sensor_id];
    double likelihood_s1 = (observation == 1) ? p_acc : (1.0 - p_acc);
    double likelihood_s0 = (observation == 1) ? (1.0 - p_acc) : p_acc;

    double unnorm_s1 = likelihood_s1 * (*belief);
    double unnorm_s0 = likelihood_s0 * (1.0 - (*belief));
    double total = unnorm_s1 + unnorm_s0;

    if (total > 0.0) {
        *belief = unnorm_s1 / total;
    }
}

int select_action_greedy(double belief, const int *costs, int budget_left, const double *acc_map) {
    int best_sensor = -1;
    double max_score = -1e9;
    double h_current = entropy_binary(belief);

    for (int i = 0; i < SENSOR_COUNT; i++) {
        if (costs[i] > budget_left) continue;
        double score = (acc_map[i] * h_current) / ((double)costs[i] + 1e-5);
        if (score > max_score) {
            max_score = score;
            best_sensor = i;
        }
    }

    return best_sensor;
}

static double oracle_terminal_value(double belief) {
    return fmax(belief, 1.0 - belief);
}

void build_oracle_table(double *value_table, const double *acc_map, const int *costs) {
    for (int i = 0; i < BELIEF_GRID; i++) {
        double belief = (double)i / (BELIEF_GRID - 1);
        value_table[i] = oracle_terminal_value(belief);
    }

    for (int step = 1; step <= HORIZON; step++) {
        double prev_values[BELIEF_GRID];
        memcpy(prev_values, value_table, sizeof(prev_values));

        for (int i = 0; i < BELIEF_GRID; i++) {
            double belief = (double)i / (BELIEF_GRID - 1);
            double best_value = -1e9;

            for (int action = 0; action < SENSOR_COUNT; action++) {
                double expected = 0.0;
                for (int obs = 0; obs < STATE_COUNT; obs++) {
                    double p_observe = (obs == 1)
                        ? (belief * acc_map[action] + (1.0 - belief) * (1.0 - acc_map[action]))
                        : (belief * (1.0 - acc_map[action]) + (1.0 - belief) * acc_map[action]);

                    double next_belief = belief;
                    bayes_update(&next_belief, action, obs, acc_map);
                    int idx = nearest_belief_index(next_belief);
                    expected += p_observe * (0.9 * prev_values[idx]);
                }

                double reward = oracle_terminal_value(belief) + expected - 0.12 * costs[action];
                if (reward > best_value) {
                    best_value = reward;
                }
            }

            value_table[i] = best_value;
        }
    }
}

double wasserstein_1_distance(const double *p, const double *q, int n) {
    double cdf_p = 0.0;
    double cdf_q = 0.0;
    double total = 0.0;

    for (int i = 0; i < n; i++) {
        cdf_p += p[i];
        cdf_q += q[i];
        total += fabs(cdf_p - cdf_q);
    }

    return total;
}

int load_binary_telemetry(const char *path, double *sensor_matrix, int max_rows) {
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        return 0;
    }

    int rows = 0;
    double sample[SENSOR_COUNT];

    while (rows < max_rows && fread(sample, sizeof(double), SENSOR_COUNT, fp) == SENSOR_COUNT) {
        memcpy(sensor_matrix + rows * SENSOR_COUNT, sample, SENSOR_COUNT * sizeof(double));
        rows++;
    }

    fclose(fp);
    return rows;
}

int main(int argc, char **argv) {
    srand((unsigned)time(NULL));

    int costs[SENSOR_COUNT] = {1, 2, 5, 4};
    double acc_map[SENSOR_COUNT] = {0.65, 0.75, 0.90, 0.85};
    Environment env;
    env_reset(&env);

    double oracle_table[BELIEF_GRID];
    build_oracle_table(oracle_table, acc_map, costs);
    double oracle_start = oracle_table[nearest_belief_index(0.5)];

    double expected_distribution[STATE_COUNT] = {0.5, 0.5};
    double observed_distribution[STATE_COUNT] = {0.7, 0.3};
    double wasserstein_gap = wasserstein_1_distance(expected_distribution, observed_distribution, STATE_COUNT);

    double sensor_matrix[SAMPLE_CAP * SENSOR_COUNT];
    int telemetry_rows = 0;
    if (argc > 1) {
        telemetry_rows = load_binary_telemetry(argv[1], sensor_matrix, SAMPLE_CAP);
    }

    long total_utility = 0;
    long total_cost_spent = 0;
    long total_accumulated = 0;

#ifdef _OPENMP
#pragma omp parallel for reduction(+: total_utility, total_cost_spent, total_accumulated) schedule(static)
#endif
    for (int ep = 0; ep < EPISODES; ep++) {
        Environment local_env = env;
        local_env.state = rand() % STATE_COUNT;
        local_env.regime = rand() % STATE_COUNT;
        local_env.drift_level = (local_env.regime == 0) ? 0.12 : 0.28;

        double belief = 0.5;
        int budget = INITIAL_BUDGET;

        while (budget > 0) {
            int action = select_action_greedy(belief, costs, budget, acc_map);
            if (action == -1) break;

            int cost = costs[action];
            budget -= cost;
            total_cost_spent += cost;

            int obs = env_observe(&local_env, action, acc_map);
            update_belief_asm(&belief, action, obs, acc_map);

            if ((ep % 250) == 0 && budget > 0) {
                switch_regime(&local_env);
            }
        }

        int pred = (belief >= 0.5) ? 1 : 0;
        int utility = (pred == local_env.state) ? 1 : -2;
        total_utility += utility;
        total_accumulated += (int)lround(belief * 100.0);
    }

    double efficiency = (double)total_utility / ((double)total_cost_spent + 1e-5);
    double mean_confidence = (double)total_accumulated / (double)(EPISODES * 100.0);

    printf("[Laboratório Híbrido C + Assembly + POMDP Oracle]\n");
    printf("Oracle de referência (grid de crença, horizonte 3): %.4f\n", oracle_start);
    printf("Gap de Wasserstein entre distribuição esperada e observada: %.4f\n", wasserstein_gap);
    printf("Telemetria binária carregada: %d amostras\n", telemetry_rows);
    printf("Utilidade Acumulada: %ld\n", total_utility);
    printf("Custo Total Gasto: %ld\n", total_cost_spent);
    printf("Eficiência da Política (U/C): %.4f\n", efficiency);
    printf("Confiança média estimada: %.4f\n", mean_confidence);

    return 0;
}