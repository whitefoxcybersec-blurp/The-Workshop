.intel_syntax noprefix
.global update_belief_asm
.text

/*
    Parâmetros da função (System V AMD64 ABI):
    RDI = ponteiro para a crença atual (double *belief)
    RSI = ID do sensor (int sensor_id)
    RDX = observação recebida (int observation)
    RCX = ponteiro para o array de acurácias (double *acc_map)
*/

update_belief_asm:
    # Carrega a crença atual (*belief) no registrador XMM0
    movsd xmm0, qword ptr [rdi]
    
    # Obtém a acurácia do sensor correspondente: p_acc = acc_map[sensor_id]
    # Cada double ocupa 8 bytes, então deslocamos sensor_id por 3 (sensor_id * 8)
    movsxd rax, esi
    lea r8, [rcx + rax*8]
    movsd xmm1, qword ptr [r8]          # xmm1 = p_acc

    # Prepara constantes para cálculo de probabilidade
    # xmm2 = 1.0 (para complementaridade)
    mov r8, 0x3FF0000000000000          # Representação hexadecimal de 1.0 em double
    movq xmm2, r8

    # Verifica a observação (RDX == 1 ou 0)
    cmp rdx, 1
    je obs_is_one

obs_is_zero:
    # Se obs == 0: likelihood_s1 = 1.0 - p_acc, likelihood_s0 = p_acc
    movsd xmm3, xmm2                    # xmm3 = 1.0
    subsd xmm3, xmm1                    # xmm3 (lik_s1) = 1.0 - p_acc
    movsd xmm4, xmm1                    # xmm4 (lik_s0) = p_acc
    jmp compute_bayes

obs_is_one:
    # Se obs == 1: likelihood_s1 = p_acc, likelihood_s0 = 1.0 - p_acc
    movsd xmm3, xmm1                    # xmm3 (lik_s1) = p_acc
    movsd xmm4, xmm2                    # xmm4 = 1.0
    subsd xmm4, xmm1                    # xmm4 (lik_s0) = 1.0 - p_acc

compute_bayes:
    # unnorm_s1 = lik_s1 * belief (xmm0)
    movsd xmm5, xmm3
    mulsd xmm5, xmm0                    # xmm5 = unnorm_s1

    # unnorm_s0 = lik_s0 * (1.0 - belief)
    movsd xmm6, xmm2                    # xmm6 = 1.0
    subsd xmm6, xmm0                    # xmm6 = 1.0 - belief
    mulsd xmm6, xmm4                    # xmm6 = unnorm_s0

    # total = unnorm_s1 + unnorm_s0
    movsd xmm7, xmm5
    addsd xmm7, xmm6                    # xmm7 = total

    # Nova crença = unnorm_s1 / total
    divsd xmm5, xmm7                    # xmm5 = nova crença

    # Salva o resultado de volta no ponteiro de crença (*belief)
    movsd qword ptr [rdi], xmm5

    ret