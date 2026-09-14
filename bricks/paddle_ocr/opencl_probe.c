#define CL_TARGET_OPENCL_VERSION 120

#include <CL/cl.h>

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ELEMENT_COUNT 1024


static void print_opencl_error(const char *operation, cl_int error)
{
    fprintf(stderr, "[OPENCL PROBE] FAIL %s returned %d\n", operation, error);
}


static void print_device_string(
    cl_device_id device,
    cl_device_info field,
    const char *label
)
{
    char value[512] = {0};
    cl_int error = clGetDeviceInfo(device, field, sizeof(value), value, NULL);

    if (error == CL_SUCCESS) {
        printf("[OPENCL PROBE] %s: %s\n", label, value);
    } else {
        print_opencl_error(label, error);
    }
}


static cl_device_id find_gpu_device(void)
{
    cl_platform_id platforms[16];
    cl_uint platform_count = 0;
    cl_int error = clGetPlatformIDs(16, platforms, &platform_count);

    if (error != CL_SUCCESS) {
        print_opencl_error("clGetPlatformIDs", error);
        return NULL;
    }

    printf("[OPENCL PROBE] OpenCL platforms: %u\n", platform_count);

    for (cl_uint index = 0; index < platform_count; ++index) {
        char platform_name[512] = {0};
        clGetPlatformInfo(
            platforms[index],
            CL_PLATFORM_NAME,
            sizeof(platform_name),
            platform_name,
            NULL
        );
        printf(
            "[OPENCL PROBE] Platform %u: %s\n",
            index,
            platform_name
        );

        cl_device_id device = NULL;
        error = clGetDeviceIDs(
            platforms[index],
            CL_DEVICE_TYPE_GPU,
            1,
            &device,
            NULL
        );
        if (error == CL_SUCCESS) {
            return device;
        }
        if (error != CL_DEVICE_NOT_FOUND) {
            print_opencl_error("clGetDeviceIDs", error);
        }
    }

    fprintf(stderr, "[OPENCL PROBE] FAIL no OpenCL GPU device found\n");
    return NULL;
}


static void print_build_log(cl_program program, cl_device_id device)
{
    size_t log_size = 0;
    clGetProgramBuildInfo(
        program,
        device,
        CL_PROGRAM_BUILD_LOG,
        0,
        NULL,
        &log_size
    );
    if (log_size == 0) {
        return;
    }

    char *log = calloc(log_size + 1, 1);
    if (log == NULL) {
        return;
    }

    clGetProgramBuildInfo(
        program,
        device,
        CL_PROGRAM_BUILD_LOG,
        log_size,
        log,
        NULL
    );
    fprintf(stderr, "[OPENCL PROBE] OpenCL build log:\n%s\n", log);
    free(log);
}


int main(void)
{
    static const char *kernel_source =
        "__kernel void vector_add("
        "    __global const float *left,"
        "    __global const float *right,"
        "    __global float *output)"
        "{"
        "    size_t index = get_global_id(0);"
        "    output[index] = left[index] + right[index];"
        "}";

    cl_device_id device = find_gpu_device();
    if (device == NULL) {
        return EXIT_FAILURE;
    }

    print_device_string(device, CL_DEVICE_NAME, "Device");
    print_device_string(device, CL_DEVICE_VENDOR, "Vendor");
    print_device_string(device, CL_DEVICE_VERSION, "Device version");
    print_device_string(device, CL_DRIVER_VERSION, "Driver version");
    print_device_string(device, CL_DEVICE_OPENCL_C_VERSION, "OpenCL C version");

    cl_int error = CL_SUCCESS;
    cl_context context = clCreateContext(NULL, 1, &device, NULL, NULL, &error);
    if (error != CL_SUCCESS) {
        print_opencl_error("clCreateContext", error);
        return EXIT_FAILURE;
    }

    cl_command_queue queue = clCreateCommandQueue(
        context,
        device,
        CL_QUEUE_PROFILING_ENABLE,
        &error
    );
    if (error != CL_SUCCESS) {
        print_opencl_error("clCreateCommandQueue", error);
        clReleaseContext(context);
        return EXIT_FAILURE;
    }

    cl_program program = clCreateProgramWithSource(
        context,
        1,
        &kernel_source,
        NULL,
        &error
    );
    if (error != CL_SUCCESS) {
        print_opencl_error("clCreateProgramWithSource", error);
        clReleaseCommandQueue(queue);
        clReleaseContext(context);
        return EXIT_FAILURE;
    }

    error = clBuildProgram(program, 1, &device, NULL, NULL, NULL);
    if (error != CL_SUCCESS) {
        print_opencl_error("clBuildProgram", error);
        print_build_log(program, device);
        clReleaseProgram(program);
        clReleaseCommandQueue(queue);
        clReleaseContext(context);
        return EXIT_FAILURE;
    }

    cl_kernel kernel = clCreateKernel(program, "vector_add", &error);
    if (error != CL_SUCCESS) {
        print_opencl_error("clCreateKernel", error);
        clReleaseProgram(program);
        clReleaseCommandQueue(queue);
        clReleaseContext(context);
        return EXIT_FAILURE;
    }

    float left[ELEMENT_COUNT];
    float right[ELEMENT_COUNT];
    float output[ELEMENT_COUNT] = {0};
    for (size_t index = 0; index < ELEMENT_COUNT; ++index) {
        left[index] = (float)index * 0.5f;
        right[index] = (float)index * 0.25f + 3.0f;
    }

    const size_t buffer_size = sizeof(left);
    cl_mem left_buffer = clCreateBuffer(
        context,
        CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
        buffer_size,
        left,
        &error
    );
    if (error != CL_SUCCESS) {
        print_opencl_error("clCreateBuffer(left)", error);
        goto cleanup_kernel;
    }

    cl_mem right_buffer = clCreateBuffer(
        context,
        CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
        buffer_size,
        right,
        &error
    );
    if (error != CL_SUCCESS) {
        print_opencl_error("clCreateBuffer(right)", error);
        goto cleanup_left_buffer;
    }

    cl_mem output_buffer = clCreateBuffer(
        context,
        CL_MEM_WRITE_ONLY,
        buffer_size,
        NULL,
        &error
    );
    if (error != CL_SUCCESS) {
        print_opencl_error("clCreateBuffer(output)", error);
        goto cleanup_right_buffer;
    }

    error = clSetKernelArg(kernel, 0, sizeof(left_buffer), &left_buffer);
    error |= clSetKernelArg(kernel, 1, sizeof(right_buffer), &right_buffer);
    error |= clSetKernelArg(kernel, 2, sizeof(output_buffer), &output_buffer);
    if (error != CL_SUCCESS) {
        print_opencl_error("clSetKernelArg", error);
        goto cleanup_output_buffer;
    }

    const size_t global_size = ELEMENT_COUNT;
    cl_event kernel_event = NULL;
    error = clEnqueueNDRangeKernel(
        queue,
        kernel,
        1,
        NULL,
        &global_size,
        NULL,
        0,
        NULL,
        &kernel_event
    );
    if (error != CL_SUCCESS) {
        print_opencl_error("clEnqueueNDRangeKernel", error);
        goto cleanup_output_buffer;
    }

    error = clEnqueueReadBuffer(
        queue,
        output_buffer,
        CL_TRUE,
        0,
        buffer_size,
        output,
        1,
        &kernel_event,
        NULL
    );
    if (error != CL_SUCCESS) {
        print_opencl_error("clEnqueueReadBuffer", error);
        clReleaseEvent(kernel_event);
        goto cleanup_output_buffer;
    }

    cl_ulong started_ns = 0;
    cl_ulong finished_ns = 0;
    clGetEventProfilingInfo(
        kernel_event,
        CL_PROFILING_COMMAND_START,
        sizeof(started_ns),
        &started_ns,
        NULL
    );
    clGetEventProfilingInfo(
        kernel_event,
        CL_PROFILING_COMMAND_END,
        sizeof(finished_ns),
        &finished_ns,
        NULL
    );
    clReleaseEvent(kernel_event);

    float maximum_error = 0.0f;
    for (size_t index = 0; index < ELEMENT_COUNT; ++index) {
        const float expected = left[index] + right[index];
        const float current_error = fabsf(output[index] - expected);
        if (current_error > maximum_error) {
            maximum_error = current_error;
        }
    }

    if (maximum_error > 0.0001f) {
        fprintf(
            stderr,
            "[OPENCL PROBE] FAIL result validation max_error=%g\n",
            maximum_error
        );
        error = CL_INVALID_VALUE;
    } else {
        const double kernel_ms = (double)(finished_ns - started_ns) / 1000000.0;
        printf(
            "[OPENCL PROBE] PASS elements=%d max_error=%g kernel_ms=%.6f\n",
            ELEMENT_COUNT,
            maximum_error,
            kernel_ms
        );
    }

cleanup_output_buffer:
    clReleaseMemObject(output_buffer);
cleanup_right_buffer:
    clReleaseMemObject(right_buffer);
cleanup_left_buffer:
    clReleaseMemObject(left_buffer);
cleanup_kernel:
    clReleaseKernel(kernel);
    clReleaseProgram(program);
    clReleaseCommandQueue(queue);
    clReleaseContext(context);

    return error == CL_SUCCESS ? EXIT_SUCCESS : EXIT_FAILURE;
}
