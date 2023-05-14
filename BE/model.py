import torch
from torch import nn


class ConvBlock(nn.Module):
    def __init__(
        self,
        in_channels, # C*W*H ví dụ image rgb có C = 3 
        out_channels, # có bao nhiêu kernel để học 
        discriminator=False,
        use_act=True, # active
        use_bn=True,  # batchnorm
        **kwargs, #key arguments: đối số từ khoá
    ):
        super().__init__()
        self.use_act = use_act
        self.cnn = nn.Conv2d(in_channels, out_channels, **kwargs, bias=not use_bn)
        self.bn = nn.BatchNorm2d(out_channels) if use_bn else nn.Identity()
        self.act = (
            nn.LeakyReLU(0.2, inplace=True)
            if discriminator
            else nn.PReLU(num_parameters=out_channels)
        )

    def forward(self, x):
        return self.act(self.bn(self.cnn(x))) if self.use_act else self.bn(self.cnn(x))


class UpsampleBlock(nn.Module):
    def __init__(self, in_c, scale_factor):
        super().__init__()
        self.conv = nn.Conv2d(in_c, in_c * scale_factor ** 2, 3, 1, 1)
        self.ps = nn.PixelShuffle(scale_factor)  # in_c * 4, H, W --> in_c, H*2, W*2
        self.act = nn.PReLU(num_parameters=in_c)

    def forward(self, x):
        return self.act(self.ps(self.conv(x)))

class MultiScaleStripAttn(nn.Module):
    def __init__(self,
                 channels):
        super(MultiScaleStripAttn, self).__init__()
        self.dwconv = nn.Conv2d(
            in_channels=channels,
            out_channels=channels,
            kernel_size=5,
            padding=2,
            groups=channels
        )
        self.scale_7 = nn.Sequential(
            nn.Conv2d(
                in_channels=channels,
                out_channels=channels,
                kernel_size=(1, 7),
                padding=(0, 3),
                groups=channels
            ),
            nn.Conv2d(
                in_channels=channels,
                out_channels=channels,
                kernel_size=(7, 1),
                padding=(3, 0),
                groups=channels
            )
        )
        self.scale_11 = nn.Sequential(
            nn.Conv2d(
                in_channels=channels,
                out_channels=channels,
                kernel_size=(1, 11),
                padding=(0, 5),
                groups=channels
            ),
            nn.Conv2d(
                in_channels=channels,
                out_channels=channels,
                kernel_size=(11, 1),
                padding=(5, 0),
                groups=channels
            )
        )
        self.scale_21 = nn.Sequential(
            nn.Conv2d(
                in_channels=channels,
                out_channels=channels,
                kernel_size=(1, 21),
                padding=(0, 10),
                groups=channels
            ),
            nn.Conv2d(
                in_channels=channels,
                out_channels=channels,
                kernel_size=(21, 1),
                padding=(10, 0),
                groups=channels
            )
        )
        self.pwconv = nn.Conv2d(
            in_channels=channels,
            out_channels=channels,
            kernel_size=1
        )

    def forward(self, x):
        base_weight = self.dwconv(x)
        weight1 = self.scale_7(base_weight)
        weight2 = self.scale_11(base_weight)
        weight3 = self.scale_21(base_weight)
        weight = base_weight + weight1 + weight2 + weight3
        weight = self.pwconv(weight)

        return x * weight

class ResidualBlock(nn.Module):
    def __init__(self, in_channels):
        super().__init__()
        self.block1 = ConvBlock(
            in_channels,
            in_channels,
            kernel_size=3,
            stride=1,
            padding=1
        )
        self.block2 = ConvBlock(
            in_channels,
            in_channels,
            kernel_size=3,
            stride=1,
            padding=1,
            use_act=False,
        )

    def forward(self, x):
        out = self.block1(x)
        out = self.block2(out)
        return out + x # skip connection tránh mất mát dữ liệu


class Generator(nn.Module):
    def __init__(self, in_channels=3, num_channels=64, num_blocks=16):
        super().__init__()
        self.initial = ConvBlock(in_channels, num_channels, kernel_size=9, stride=1, padding=4, use_bn=False)
        self.residuals1 = nn.Sequential(*[MultiScaleStripAttn(num_channels) for _ in range(num_blocks)])
        self.residuals2 = nn.Sequential(*[MultiScaleStripAttn(num_channels) for _ in range(num_blocks)])
        # arr = [] 
        # for _ in range(num_block):
        #   arr.append(ResidualBlock(num_channels))
        # *[1,2] => 1,2
        # *arr =>
        self.convblock = ConvBlock(num_channels, num_channels, kernel_size=3, stride=1, padding=1, use_act=False)
        self.upsamples = nn.Sequential(UpsampleBlock(num_channels, 2), UpsampleBlock(num_channels, 2))
        self.final = nn.Conv2d(num_channels, in_channels, kernel_size=9, stride=1, padding=4)

    def forward(self, x):
        initial = self.initial(x)
        x = self.residuals1(initial) + self.residuals2(initial)
        x = self.convblock(x) + initial
        x = self.upsamples(x)
        return torch.tanh(self.final(x))