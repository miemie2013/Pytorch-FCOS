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

from config import *
from model.decode_np import Decode
from model.fcos import *
from model.head import *
from model.neck import *
from model.resnet import *
from tools.cocotools import get_classes

import logging
FORMAT = '%(asctime)s-%(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)



# 6G的卡，训练时如果要预测，则设置use_gpu = False，否则显存不足。
use_gpu = False
use_gpu = True


if __name__ == '__main__':
    cfg = FCOS_R50_FPN_Multiscale_2x_Config()


    # 读取的模型
    model_path = cfg.test_cfg['model_path']

    # 分数阈值和nms_iou阈值
    conf_thresh = cfg.test_cfg['conf_thresh']
    nms_thresh = cfg.test_cfg['nms_thresh']

    # 是否给图片画框。
    draw_image = cfg.test_cfg['draw_image']

    all_classes = get_classes(cfg.classes_path)
    num_classes = len(all_classes)


    # 创建模型
    Backbone = select_backbone(cfg.backbone_type)
    backbone = Backbone(**cfg.backbone)
    Fpn = select_fpn(cfg.fpn_type)
    fpn = Fpn(**cfg.fpn)
    Head = select_head(cfg.head_type)
    head = Head(num_classes=num_classes, **cfg.head)
    fcos = FCOS(backbone, fpn, head)
    if use_gpu:
        fcos = fcos.cuda()
    fcos.load_state_dict(torch.load(model_path))
    fcos.eval()  # 必须调用model.eval()来设置dropout和batch normalization layers在运行推理前，切换到评估模式. 不这样做的化会产生不一致的推理结果.

    _decode = Decode(conf_thresh, nms_thresh, fcos, all_classes, use_gpu)

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


