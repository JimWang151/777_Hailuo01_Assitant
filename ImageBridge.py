# Made by JimWang for ComfyUI
# 02/04/2023

import torch
import random
import folder_paths
import uuid
import json
import urllib.request
import urllib.parse
import os
import numpy as np

import comfy.utils
from comfy.cli_args import args

from PIL import Image, ImageOps, ImageSequence, ImageFile
from PIL.PngImagePlugin import PngInfo
import collections
from torchvision.transforms import ToPILImage,ToTensor
import torchvision.transforms as T

from PIL import Image, ImageDraw

import collections

class ImageBridge:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "frame_nums": ("INT", {"default":2}),
                "frame_width": ("INT", {"default": 5,
                                        "min": 5,
                                        "max": 50,
                                        "step": 5,
                                        "display": "number"}),
            },
        }

    RETURN_TYPES = ("JOB",)
    RETURN_NAMES = ("job",)
    FUNCTION = "Canvas_Setting"
    OUTPUT_NODE = True
    CATEGORY = "Hailuo01"
    DESCRIPTION = "Basic config for your frame."


    def Canvas_Setting(self, frame_nums,frame_width):
        # 初始化画布高度和宽度
        canvas_height = 1024
        canvas_width = 0
        image_count=frame_nums
        # 初始化图片尺寸计数器
        image_counts = collections.OrderedDict([
            ('1024x768', 0),
            ('512x768', 0),
            ('1024x1024', 0)
        ])

        # 初始化图片尺寸列表
        image_sizes = []

        # 规则5：画布最左侧必须是1024*768的纵向规格
        if image_count > 0:
            image_counts['1024x768'] += 1
            canvas_width += 768
            image_count -= 1
            image_sizes.append({"width": 768, "height": 1024})
            alternate = True
        # 规则6和规则7：尽可能考虑2个横向规格进行堆叠的‘过度规格’
        while image_count > 0:
            if image_count >= 2 and (image_counts['512x768'] % 2 == 0):
                # 使用两张512x768的图片
                image_counts['512x768'] += 2
                canvas_width += 768
                image_count -= 2
                image_sizes.append({"width": 768, "height": 512})
                image_sizes.append({"width": 768, "height": 512})
            elif alternate and image_count >= 1:
                # 使用一张1024x1024的图片
                image_counts['1024x1024'] += 1
                canvas_width += 1024
                image_count -= 1
                image_sizes.append({"width": 1024, "height": 1024})
                alternate = False
            elif not alternate and image_count >= 1:
                # 使用一张1024x768的图片
                image_counts['1024x768'] += 1
                canvas_width += 768
                image_count -= 1
                image_sizes.append({"width": 768, "height": 1024})
                alternate = True
            else:
                # 剩余一张图片时，选择当前较少使用的1024x512或1024x768
                if image_counts['1024x1024'] <= image_counts['1024x768']:
                    image_counts['1024x1024'] += 1
                    canvas_width += 1024
                    image_sizes.append({"width": 1024, "height": 1024})
                else:
                    image_counts['1024x768'] += 1
                    canvas_width += 768
                    image_sizes.append({"width": 768, "height": 1024})
                image_count -= 1


        # 返回结果

        return (image_sizes,)


class ImageStitcher:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    INPUT_IS_LIST = (True,)
    FUNCTION = "stitch_images"
    CATEGORY = "Hailuo01"

    import torch

    def preprocess_image(self,image):


        # 检查是否有批次维度 (e.g., [1, H, W, 3])
        if len(image.shape) == 4 and image.shape[0] == 1:
            image = image.squeeze(0)  # 移除批次维度

        # 检查是否是 [H, W, 3] 格式 (通道在最后)
        if len(image.shape) == 3 and image.shape[-1] == 3:
            image = image.permute(2, 0, 1)  # 转换为 [3, H, W]

        # 如果图片是 float32 类型，归一化到 [0, 255] 并转换为 uint8
        if image.dtype == torch.float32:
            image = (image * 255).clamp(0, 255).to(torch.uint8)

        return image

    def add_outer_frame(self, image, border_width=20, frame_color=(50, 50, 50), perforation_diameter=15,
                        perforation_spacing=60):
        """
        给图片添加边框样式

        """
        if isinstance(image, torch.Tensor):
            if image.max() <= 1.0:
                image = ToPILImage()(image)
            else:
                image = ToPILImage()(image / 255)

        img_width, img_height = image.size
        perforation_radius = perforation_diameter // 2
        canvas_width = img_width + 2 * border_width
        canvas_height = img_height + 2 * border_width
        canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
        canvas.paste(image, (border_width, border_width))
        draw = ImageDraw.Draw(canvas)

        # 绘制黑色边框
        draw.rectangle(
            [(0, 0), (canvas_width - 1, canvas_height - 1)],
            outline=frame_color,
            width=border_width
        )

        # 绘制 perforation 样式
        for y in range(border_width + perforation_radius, canvas_height - border_width - perforation_radius,
                       perforation_diameter + perforation_spacing):
            draw.ellipse(
                [
                    (border_width // 2 - perforation_radius, y - perforation_radius),
                    (border_width // 2 + perforation_radius, y + perforation_radius)
                ],
                fill=(200, 200, 200)
            )
            draw.ellipse(
                [
                    (canvas_width - border_width // 2 - perforation_radius, y - perforation_radius),
                    (canvas_width - border_width // 2 + perforation_radius, y + perforation_radius)
                ],
                fill=(200, 200, 200)
            )
        for x in range(border_width + perforation_radius, canvas_width - border_width,
                       perforation_diameter + perforation_spacing):
            draw.ellipse(
                [
                    (x - perforation_radius, border_width // 2 - perforation_radius),
                    (x + perforation_radius, border_width // 2 + perforation_radius)
                ],
                fill=(200, 200, 200)
            )
            draw.ellipse(
                [
                    (x - perforation_radius, canvas_height - border_width // 2 - perforation_radius),
                    (x + perforation_radius, canvas_height - border_width // 2 + perforation_radius)
                ],
                fill=(200, 200, 200)
            )

        result = ToTensor()(canvas) * 255
        # 确保范围正确
        result = result.clamp(0, 255)

        return result

    def add_inner_frame(self, image, wline, direction, frame_width=6, frame_color=(50, 50, 50)):


        # 确保形状为 (3, H, W)
        if len(image.shape) == 4 and image.shape[-1] == 3:
            # 调整形状从 (1, H, W, C) 到 (C, H, W)
            image = image.permute(0, 3, 1, 2)[0]
        elif len(image.shape) != 3 or image.shape[0] != 3:
            raise ValueError(f"Expected image shape (3, H, W), but got {image.shape}")

        frame_color = torch.tensor(frame_color, dtype=torch.uint8).view(3, 1, 1)
        _, height, width = image.shape
        framed_image = image.clone()

        if direction == "horizontal":
            framed_image[:, :, width - wline - frame_width // 2: width - wline + frame_width // 2] = frame_color
        elif direction == "vertical":
            framed_image[:, height // 2 - frame_width // 2: height // 2 + frame_width // 2, :] = frame_color
        else:
            raise ValueError("Invalid direction specified for inner frame.")


        return framed_image

    def stitch_images(self, images):


        for idx, img in enumerate(images):
            # 打印每张图片的基本信息

            # 移除批次维度（如果存在）
            if img.shape[0] == 1:
                img = img.squeeze(0)  # 从 [1, H, W, C] -> [H, W, C]

            # 如果是 float32 数据，将其从 [0, 1] 映射到 [0, 255]
            if isinstance(img, torch.Tensor) and img.dtype == torch.float32:
                img = img.clamp(0, 1) * 255  # 从 [0, 1] 映射到 [0, 255]
                img = img.to(torch.uint8)  # 转换为 uint8 类型

        processed_images = []
        for img in images:
            img = self.preprocess_image(img)
            if len(img.shape) == 4 and img.shape[-1] == 3:
                img = img.permute(0, 3, 1, 2)[0]  # 调整到 (C, H, W)
            elif len(img.shape) != 3 or img.shape[0] != 3:
                raise ValueError(f"Invalid image shape: {img.shape}")
            processed_images.append(img)

        vertical_images = [img for img in processed_images if img.shape[1] == 1024]
        horizontal_images = [img for img in processed_images if img.shape[1] == 512]

        if len(horizontal_images) % 2 != 0:
            raise ValueError("Number of horizontal images is odd.")

        stitched_images = []

        for i in range(0, len(horizontal_images), 2):
            img1 = horizontal_images[i]
            img2 = horizontal_images[i + 1]
            new_image = torch.cat((img1, img2), dim=1)
            new_image = self.add_inner_frame(new_image, 0, direction="vertical")
            stitched_images.append(new_image)

        all_vertical_images = vertical_images + stitched_images
        if not all_vertical_images:
            raise ValueError("No images with height 1024 found.")

        final_image = all_vertical_images.pop(0)

        i = 0
        while all_vertical_images:
            next_image = all_vertical_images.pop(0)
            _, _, wline = next_image.shape
            final_image = torch.cat((final_image, next_image), dim=2)
            final_image = self.add_inner_frame(final_image, wline, direction="horizontal")

        result = self.add_outer_frame(final_image, 40)
        if not isinstance(result, torch.Tensor):
            result = torch.tensor(result)
        result = result.permute(1, 2, 0)  # 从 [3, H, W] 变为 [H, W, 3]
        result = result.unsqueeze(0)  # 添加 batch 维度，变为 [1, H, W, 3]

        result_normalized = result / 255.0  # 正规化到 [0, 1]
        result_normalized = torch.clamp(result_normalized, 0.0, 1.0)  # 确保范围合法
        result_normalized = result_normalized.to(torch.float32)  # 转换为 float32

        # 返回归一化的 Tensor
        return (result_normalized,)



class PromptRefine:
        def __init__(self):
            pass

        @classmethod
        def INPUT_TYPES(s):
            return {
                "required": {
                    "character": ("STRING", {"multiline": True,  "tooltip": "The text to be encoded."}),
                    "scenes" : ("STRING", {"multiline": True,  "tooltip": "The text to be encoded."}),
                    "atmosphere" : ("STRING", {"multiline": True,  "tooltip": "The text to be encoded."}),
                    "width": ("INT",{"default": 512}),
                    "height": ("INT",{"default": 512}),
                    "step": ("INT", {"default": 1}),
                },
            }

        RETURN_TYPES = ("STRING",)
        RETURN_NAMES = ("prompt",)
        FUNCTION = "refine"
        OUTPUT_NODE = True
        CATEGORY = "Hailuo01"
        DESCRIPTION = "Generate prompt."

        def refine(self, step, character,scenes,atmosphere,width,height):
            # 初始化画布高度和宽度

            prompt="raw photo,(shengdan),";

            prompt+=self.getShotStyle(step,width,height)
            # 返回结果
            prompt+=self.getAperture(step,width,height)
            prompt+=character+" with happy expression,"+self.getPoseAndFacing(step,width,height,atmosphere)
            prompt += scenes
            prompt += self.getFocalLength(step,width, height)
            prompt += "atmosphere of "+atmosphere
            prompt+=self.getLightCondition(step,width,height,scenes)
            print(f"final prompt: {prompt}")
            return (prompt,)

        def getShotStyle(self,step,width,height):
            # 获取镜头类型
            result = ""  # 初始化结果字符串为空
            if height==1024 :
                result="full body shot,perspective Compression,"
            # 检查是否满足特定的条件，并追加相应的字符串
            if width == 1024 and step % 2 == 0:  # 检查step是否可以被2整除
                result += "side view,"
            if width == 768 and height == 512:
                result = "(half body:1.3),"
                if step % 2 ==0:
                    result="Close-up portrait,"
            # 返回结果
            return result


        def getAperture(self,step, width,height,round=1):
            # 获取光圈
            result=""
            if height == 1024:
                result="f/10,"
            if height == 1024 and width ==1024 :
                result = "f/5.6-f8,"
            if width == 768 and height == 512 :
                result = "f/11,"
                if step % 2 ==0:
                    result ="f/3-f/6,"
            # 返回结果
            return result

        def getFocalLength(self,step, width,height,round=1):
            # 获取焦距
            result = ""
            if height == 1024:
                result=",50mm,"
                if height == 1024 and width == 1024:
                    result = ",85mm,"
            if width == 768 and height == 512 :
                result = ",85mm,"
                if step % 2 ==0:
                    result =",200mm,"
            # 返回结果

            return result

        def getPoseAndFacing(self,step, width,height,atmosphere):
            # 聚焦肯虚化
            result=""
            if height == 1024:
                result=",natural waist pose,natural leg pose,natural face side,clothes fit with "+atmosphere+","
            if width == 768 and height == 512 :
                result = ",looking somewhere,"
                if step % 2 ==0:
                    result =","
            # 返回结果
            return result
        def getLightCondition(self,step, width,height,scenes):
            # 聚焦肯虚化
            result=",enough lighting,outdoor natural light,"

            # 返回结果
            return result