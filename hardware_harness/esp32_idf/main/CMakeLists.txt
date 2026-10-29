idf_component_register(SRCS "main.c" INCLUDE_DIRS "." PRIV_REQUIRES esp_timer esp_hw_support freertos mbedtls)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -Wno-unused-function -Wno-unused-variable -Wno-misleading-indentation)
