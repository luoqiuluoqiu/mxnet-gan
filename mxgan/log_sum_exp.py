"""Customized operator for log_sum_exp using NDArray GPU API"""

import numpy as np
import mxnet as mx


class LogSumExpOp(mx.operator.CustomOp):
    """Implementation of log sum exp for numerical stability
    """
    def __init__(self, axis):
        self.axis = axis

    def forward(self, is_train, req, in_data, out_data, aux):
        x = in_data[0]
        max_x = mx.nd.max_axis(x, axis=self.axis, keepdims=True)
        sum_x = mx.nd.sum_axis(mx.nd.exp(x - max_x), axis=self.axis, keepdims=True)
        y = mx.nd.log(sum_x) + max_x
        y = y.reshape(out_data[0].shape)
        self.assign(out_data[0], req[0], y)

    def backward(self, req, out_grad, in_data, out_data, in_grad, aux):
        y = out_grad[0]
        x = in_data[0]
        max_x = mx.nd.max_axis(x, axis=self.axis, keepdims=True)
        y = y.reshape(max_x.shape)
        x = mx.nd.exp(x - max_x)
        prob = x / mx.nd.sum_axis(x, axis=self.axis, keepdims=True)
        self.assign(in_grad[0], req[0], prob * y)


@mx.operator.register("log_sum_exp")
class LogSumExpProp(mx.operator.CustomOpProp):
    def __init__(self, axis, keepdims=False):
        super(LogSumExpProp, self).__init__(need_top_grad=True)
        self.axis = int(axis)
        self.keepdims = keepdims in ('True',)

    def list_arguments(self):
        return ['data']

    def list_outputs(self):
        return ['output']

    def infer_shape(self, in_shape):
        data_shape = in_shape[0]
        oshape = []
        for i, x in enumerate(data_shape):
            if i == self.axis:
                if self.keepdims:
                    oshape.append(1)
            else:
                oshape.append(x)
        return [data_shape], [tuple(oshape)], []

    def create_operator(self, ctx, shapes, dtypes):
        return LogSumExpOp(self.axis)


def log_sum_exp(in_sym, axis, keepdims=False, name="log_sum_exp"):
    return mx.symbol.Custom(in_sym, name=name,
                            op_type="log_sum_exp",
                            axis=axis, keepdims=keepdims)


# test case latter
def np_softmax(x, axis):
    max_x = np.max(x, axis=axis, keepdims=True)
    x = np.exp(x - max_x)
    x = x / np.sum(x, axis=axis, keepdims=True)
    return x



def np_log_sum_exp(x, axis, keepdims=False):
    max_x = np.max(x, axis=axis, keepdims=True)
    x = np.log(np.sum(np.exp(x - max_x), axis=axis, keepdims=True))
    x = x + max_x
    if not keepdims:
        x = np.squeeze(x, axis=axis)
    return x


def test_log_sum_exp():
    xpu = mx.gpu()
    shape = (2, 2, 100)
    axis = 2
    keepdims = True
    X = mx.sym.Variable('X')
    Y = log_sum_exp(X, axis=axis, keepdims=keepdims)
    x = mx.nd.array(np.random.normal(size=shape))
    x[:] = 1
    xgrad = mx.nd.empty(x.shape)
    exec1 = Y.bind(xpu, args = [x], args_grad = {'X': xgrad})
    exec1.forward()
    y = exec1.outputs[0]
    np.testing.assert_allclose(
        y.asnumpy(),
        np_log_sum_exp(x.asnumpy(), axis=axis, keepdims=keepdims))
    y[:] = 1
    exec1.backward([y])
    np.testing.assert_allclose(
        xgrad.asnumpy(),
        np_softmax(x.asnumpy(), axis=axis) * y.asnumpy())

if __name__ == "__main__":
    test_log_sum_exp()
