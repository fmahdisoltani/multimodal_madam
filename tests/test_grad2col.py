import torch
import torch.nn as nn

from torchsso.utils import *
from torchsso.autograd import save_batched_grads


def test_grad2col_conv_nd(ndim=2, n=10, c_in=3, c_out=5, k=3, s=2, p=1, d=28, thr=1e-6):

    if ndim == 1:
        x = torch.randn(n, c_in, d)
        conv = nn.Conv1d(c_in, c_out, kernel_size=k, stride=s, padding=p, bias=False)
    elif ndim == 2:
        x = torch.randn(n, c_in, d, d)
        conv = nn.Conv2d(c_in, c_out, kernel_size=k, stride=s, padding=p, bias=False)
    else:
        x = torch.randn(n, c_in, d, d, d)
        conv = nn.Conv3d(c_in, c_out, kernel_size=k, stride=s, padding=p, bias=False)

    def backward_postprocess(module, grad_input, grad_output):
        grad_output = grad_output[0].clone().detach()
        setattr(module, 'grad_output', grad_output)

    conv.register_backward_hook(backward_postprocess)

    with save_batched_grads(conv):
        y = conv(x)
        err = y - torch.randn_like(y)
        loss = torch.sum(err * err) / 2 / len(x)
        loss.backward()

    W = conv.weight
    gW = W.grads.reshape(n, c_out, -1)
    Mx = x.view(n, c_in, -1)
    gy = getattr(conv, 'grad_output')

    # grad2col
    Mgy = grad2col(gy, conv, x.size()[2:])

    # matmul as gradient calculation
    gW_test = torch.einsum('bik,bjk->bij', Mgy, Mx)
    gW_test = gW_test.view(n, c_out, -1, c_in)
    gW_test = gW_test.transpose(2, 3).reshape(n, c_out, -1)

    error = gW_test - gW
    ratio = error.norm() / gW.norm()

    assert ratio < thr


def test_grad2col_conv_transpose_nd(ndim=2, n=10, c_in=5, c_out=3, k=3, s=2, p=1, d=14, thr=1e-6):

    if ndim == 1:
        x = torch.randn(n, c_in, d)
        conv_transpose = nn.ConvTranspose1d(c_in, c_out, kernel_size=k, stride=s, padding=p, bias=False)
    elif ndim == 2:
        x = torch.randn(n, c_in, d, d)
        conv_transpose = nn.ConvTranspose2d(c_in, c_out, kernel_size=k, stride=s, padding=p, bias=False)
    else:
        x = torch.randn(n, c_in, d, d, d)
        conv_transpose = nn.ConvTranspose3d(c_in, c_out, kernel_size=k, stride=s, padding=p, bias=False)

    def backward_postprocess(module, grad_input, grad_output):
        grad_output = grad_output[0].clone().detach()
        setattr(module, 'grad_output', grad_output)

    conv_transpose.register_backward_hook(backward_postprocess)

    with save_batched_grads(conv_transpose):
        y = conv_transpose(x)
        err = y - torch.randn_like(y)
        loss = torch.sum(err * err) / 2 / len(x)
        loss.backward()

    W = conv_transpose.weight
    # n x c_in x (c_out)(kernel_size)
    gW = W.grads.reshape(n, c_in, -1)
    gy = getattr(conv_transpose, 'grad_output')
    # n x c_out x output_size
    Mgy = gy.view(n, c_out, -1)

    # grad2col
    # n x (c_in)(kernel_size) x output_size
    Mx = grad2col(x, conv_transpose)

    # matmul as gradient calculation
    # n x (c_in)(kernel_size) x c_out
    gW_test = torch.einsum('bik,bjk->bij', Mx, Mgy)
    # n x c_in x kernel_size x c_out
    gW_test = gW_test.view(n, c_in, -1, c_out)
    # n x c_in x (c_out)(kernel_size)
    gW_test = gW_test.transpose(2, 3).reshape(n, c_in, -1)

    error = gW_test - gW
    ratio = error.norm() / gW.norm()

    assert ratio < thr


if __name__ == '__main__':
    c_in, c_out = 3, 5
    for k in range(1, 5):
        for s in range(1, 5):
            for p in range(1, k):
                kwargs = dict(k=k, s=s, p=p)
                print(kwargs)
                test_grad2col_conv_transpose_nd(ndim=1, **kwargs)
                test_grad2col_conv_transpose_nd(ndim=2, **kwargs)
                test_grad2col_conv_transpose_nd(ndim=3, **kwargs)
                test_grad2col_conv_nd(ndim=1, **kwargs)
                test_grad2col_conv_nd(ndim=2, **kwargs)
                test_grad2col_conv_nd(ndim=3, **kwargs)