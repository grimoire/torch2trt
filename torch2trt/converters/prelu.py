from torch2trt.torch2trt import *
from torch2trt.module_test import add_module_test


@tensorrt_converter('torch.nn.functional.prelu')
def convert_prelu(ctx):
    support_dynamic_shape = False
    if hasattr(ctx, "support_dynamic_shape"):
        support_dynamic_shape = ctx.support_dynamic_shape
    input = get_arg(ctx, 'input', pos=0, default=None)
    weight = get_arg(ctx, 'weight', pos=1, default=None)
    output = ctx.method_return
    
    if not support_dynamic_shape:
        weight_shape = [1] * (len(input.shape) - 1)
        weight_shape[0] = weight.numel()
    else:
        weight_shape = [1] * len(input.shape)
        weight_shape[1] = weight.numel()
    
    input_trt = trt_(ctx.network, input)
    
   
    # y = prelu(x) = relu(x) - alpha * relu(-x)
    weight_trt = ctx.network.add_constant(weight_shape, -weight.detach().view(weight_shape).cpu().numpy()).get_output(0) # detach so considered leaf
    
    # x >= 0
    a = ctx.network.add_activation(input_trt, trt.ActivationType.RELU).get_output(0)
    
    # x <= 0
    b = ctx.network.add_unary(input_trt, trt.UnaryOperation.NEG).get_output(0)
    b = ctx.network.add_activation(b, trt.ActivationType.RELU).get_output(0)
    b = ctx.network.add_elementwise(b, weight_trt, trt.ElementWiseOperation.PROD).get_output(0)
    
    # y = a + b
    y = ctx.network.add_elementwise(a, b, trt.ElementWiseOperation.SUM)
    
    output._trt = y.get_output(0)

    
@add_module_test(torch.float32, torch.device('cuda'), [(1, 5)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 5, 3)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 5, 3, 3)])
def test_prelu_scalar():
    return torch.nn.PReLU()


@add_module_test(torch.float32, torch.device('cuda'), [(1, 5)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 5, 3)])
@add_module_test(torch.float32, torch.device('cuda'), [(1, 5, 3, 3)])
def test_prelu_vector():
    m = torch.nn.PReLU(5)
    m.weight = torch.nn.Parameter(torch.randn(5)) # randn so each channel different
    return m