// examples/use_from_c.c
// ===================================================================
// Пример использования из C.
// ===================================================================

#include <stdio.h>
#include <stdlib.h>
#include <math.h>

// Объявления C API
void* streaming_create(int n_sensors, double alpha, double n_sigma,
                       int min_count, int degree);
int streaming_push(void* handle, const double* values, int n,
                   int* out_rank, int* out_n_states, int* out_n_transitions);
int streaming_push_batch(void* handle, const double* values,
                         int n_points, int n_sensors);
int streaming_get_rank(void* handle);
int streaming_get_n_states(void* handle);
int streaming_get_n_transitions(void* handle);
void streaming_reset(void* handle);
void streaming_destroy(void* handle);
const char* streaming_version(void);


int main(void) {
    const int n_sensors = 7;
    const int n_points = 100000;

    printf("Magnus streaming v%s\n", streaming_version());
    printf("Датчиков: %d, точек: %d\n", n_sensors, n_points);

    // Создаём процессор
    void* handle = streaming_create(
        n_sensors,
        0.05,   // alpha
        1.5,    // n_sigma
        2,      // min_count
        3       // degree
    );

    if (!handle) {
        fprintf(stderr, "Ошибка создания процессора\n");
        return 1;
    }

    // Генерация синтетических данных
    double* values = (double*)malloc(n_sensors * sizeof(double));

    if (!values) {
        fprintf(stderr, "Ошибка выделения памяти\n");
        streaming_destroy(handle);
        return 1;
    }

    // Обработка
    for (int i = 0; i < n_points; i++) {
        for (int j = 0; j < n_sensors; j++) {
            values[j] = sin(0.01 * i + j) + 0.1 * ((double)rand() / RAND_MAX);
        }

        int rank, n_states, n_transitions;
        int grew = streaming_push(handle, values, n_sensors,
                                  &rank, &n_states, &n_transitions);

        if (grew && i % 10000 == 0) {
            printf("t=%d, rank=%d, states=%d, transitions=%d\n",
                   i, rank, n_states, n_transitions);
        }
    }

    printf("\nИТОГО:\n");
    printf("  Ранг:        %d\n", streaming_get_rank(handle));
    printf("  Состояний:   %d\n", streaming_get_n_states(handle));
    printf("  Переходов:   %d\n", streaming_get_n_transitions(handle));

    // Очистка
    free(values);
    streaming_destroy(handle);

    return 0;
}