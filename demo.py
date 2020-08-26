#! /usr/bin/env python
# coding=utf-8
# ================================================================
#
#   Author      : miemie2013
#   Created date: 2020-08-21 19:33:37
#   Description : pytorch_fcos
#
# ================================================================
from collections import deque
import datetime
import cv2
import os
import time
import numpy as np
import torch

from model.decode_np import Decode
from model.fcos import FCOS
from model.head import FCOSHead
from model.neck import FPN
from model.resnet import Resnet
from tools.cocotools import get_classes

import logging
FORMAT = '%(asctime)s-%(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)



# 6G的卡，训练时如果要预测，则设置use_gpu = False，否则显存不足。
use_gpu = False
use_gpu = True


if __name__ == '__main__':
    # classes_path = 'data/voc_classes.txt'
    classes_path = 'data/coco_classes.txt'
    # model_path可以是'pytorch_yolov4.pt'、'./weights/step00001000.pt'这些。
    model_path = 'pytorch_yolov4.pt'
    # model_path = './weights/step00001000.pt'

    # input_shape越大，精度会上升，但速度会下降。
    # input_shape = (320, 320)
    input_shape = (416, 416)
    # input_shape = (608, 608)

    # 验证时的分数阈值和nms_iou阈值
    conf_thresh = 0.05
    nms_thresh = 0.45

    # 是否给图片画框。不画可以提速。读图片、后处理还可以继续优化。
    draw_image = True
    # draw_image = False


    num_anchors = 3
    all_classes = get_classes(classes_path)
    num_classes = len(all_classes)

    resnet = Resnet(50)
    fpn = FPN()
    head = FCOSHead()
    fcos = FCOS(resnet, fpn, head)
    if torch.cuda.is_available():  # 如果有gpu可用，模型（包括了权重weight）存放在gpu显存里
        fcos = fcos.cuda()
    # fcos.load_state_dict(torch.load(model_path))
    fcos.eval()  # 必须调用model.eval()来设置dropout和batch normalization layers在运行推理前，切换到评估模式. 不这样做的化会产生不一致的推理结果.

    _decode = Decode(conf_thresh, nms_thresh, input_shape, fcos, all_classes)

    if not os.path.exists('images/res/'): os.mkdir('images/res/')


    path_dir = os.listdir('images/test')
    # warm up
    if use_gpu:
        for k, filename in enumerate(path_dir):
            image = cv2.imread('images/test/' + filename)
            image, boxes, scores, classes = _decode.detect_image(image, draw_image=False)
            if k == 10:
                break


    time_stat = deque(maxlen=20)
    start_time = time.time()
    end_time = time.time()
    num_imgs = len(path_dir)
    start = time.time()
    for k, filename in enumerate(path_dir):
        image = cv2.imread('images/test/' + filename)
        image, boxes, scores, classes = _decode.detect_image(image, draw_image)

        # 估计剩余时间
        start_time = end_time
        end_time = time.time()
        time_stat.append(end_time - start_time)
        time_cost = np.mean(time_stat)
        eta_sec = (num_imgs - k) * time_cost
        eta = str(datetime.timedelta(seconds=int(eta_sec)))

        logger.info('Infer iter {}, num_imgs={}, eta={}.'.format(k, num_imgs, eta))
        if draw_image:
            cv2.imwrite('images/res/' + filename, image)
            logger.info("Detection bbox results save in images/res/{}".format(filename))
    cost = time.time() - start
    logger.info('total time: {0:.6f}s'.format(cost))
    logger.info('Speed: %.6fs per image,  %.1f FPS.'%((cost / num_imgs), (num_imgs / cost)))


