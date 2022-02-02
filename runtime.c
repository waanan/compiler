#include <stdint.h>
#include <stdio.h>

int64_t read_int() {
  int64_t result;
  scanf("%lld", &result);
  return result;
}

void print_int(int64_t x) {
  printf("%lld\n", x);
}