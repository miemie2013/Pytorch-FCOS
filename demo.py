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
import threading
import argparse

from config import *
from model.decode_np import Decode
from model.fcos import *

from tools.cocotools import get_classes

import logging
FORMAT = '%(asctime)s-%(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='FCOS Infer Script')
parser.add_argument('--use_gpu', type=bool, default=True)
parser.add_argument('--config', type=int, default=2,
                    choices=[0, 1, 2],
                    help='0 -- fcos_r50_fpn_multiscale_2x.py;  1 -- fcos_rt_r50_fpn_4x.py;  2 -- fcos_rt_dla34_fpn_4x.py.')
args = parser.parse_args()
config_file = args.config
use_gpu = args.use_gpu


def read_test_data(path_dir,
                   _decode,
                   test_dic):
    for k, filename in enumerate(path_dir):
        key_list = list(test_dic.keys())
        key_len = len(key_list)
        while key_len >= 3:
            time.sleep(0.01)
            key_list = list(test_dic.keys())
            key_len = len(key_list)

        image = cv2.imread('images/test/' + filename)
        sample = _decode.process_image(np.copy(image))

        samples = [sample]
        coarsest_stride = _decode.pad_to_stride
        max_shape = np.array([data['image'].shape for data in samples]).max(
            axis=0)    # max_shape=[3, max_h, max_w]
        max_shape[1] = int(   # max_h增加到最小的能被coarsest_stride=128整除的数
            np.ceil(max_shape[1] / coarsest_stride) * coarsest_stride)
        max_shape[2] = int(   # max_w增加到最小的能被coarsest_stride=128整除的数
            np.ceil(max_shape[2] / coarsest_stride) * coarsest_stride)

        pimage, im_info = _decode.process_image_batch_transforms(sample, max_shape)
        dic = {}
        dic['image'] = image
        dic['pimage'] = pimage
        dic['im_info'] = im_info
        test_dic['%.8d' % k] = dic

def save_img(filename, image):
    cv2.imwrite('images/res/' + filename, image)

if __name__ == '__main__':
    cfg = None
    if config_file == 0:
        cfg = FCOS_R50_FPN_Multiscale_2x_Config()
    elif config_file == 1:
        cfg = FCOS_RT_R50_FPN_4x_Config()
    elif config_file == 2:
        cfg = FCOS_RT_DLA34_FPN_4x_Config()


    # 读取的模型
    model_path = cfg.test_cfg['model_path']

    # 是否给图片画框。
    draw_image = cfg.test_cfg['draw_image']
    draw_thresh = cfg.test_cfg['draw_thresh']

    all_classes = get_classes(cfg.classes_path)
    num_classes = len(all_classes)


    # 创建模型
    Backbone = select_backbone(cfg.backbone_type)
    backbone = Backbone(**cfg.backbone)
    Fpn = select_fpn(cfg.fpn_type)
    fpn = Fpn(**cfg.fpn)
    Head = select_head(cfg.head_type)
    head = Head(fcos_loss=None, nms_cfg=cfg.nms_cfg, **cfg.head)
    fcos = FCOS(backbone, fpn, head)
    if use_gpu:
        fcos = fcos.cuda()
    fcos.load_state_dict(torch.load(model_path))
    fcos.eval()  # 必须调用model.eval()来设置dropout和batch normalization layers在运行推理前，切换到评估模式。

    _decode = Decode(fcos, all_classes, use_gpu, cfg, for_test=True)

    if not os.path.exists('images/res/'): os.mkdir('images/res/')
    path_dir = os.listdir('images/test')

    # 读数据的线程
    test_dic = {}
    thr = threading.Thread(target=read_test_data,
                           args=(path_dir,
                                 _decode,
                                 test_dic))
    thr.start()

    key_list = list(test_dic.keys())
    key_len = len(key_list)
    while key_len == 0:
        time.sleep(0.01)
        key_list = list(test_dic.keys())
        key_len = len(key_list)
    dic = test_dic['%.8d' % 0]
    image = dic['image']
    pimage = dic['pimage']
    im_info = dic['im_info']


    # warm up
    if use_gpu:
        for k in range(10):
            image, boxes, scores, classes = _decode.detect_image(image, pimage, im_info, draw_image=False)


    time_stat = deque(maxlen=20)
    start_time = time.time()
    end_time = time.time()
    num_imgs = len(path_dir)
    start = time.time()
    for k, filename in enumerate(path_dir):
        key_list = list(test_dic.keys())
        key_len = len(key_list)
        while key_len == 0:
            time.sleep(0.01)
            key_list = list(test_dic.keys())
            key_len = len(key_list)
        dic = test_dic.pop('%.8d' % k)
        image = dic['image']
        pimage = dic['pimage']
        im_info = dic['im_info']

        image, boxes, scores, classes = _decode.detect_image(image, pimage, im_info, draw_image, draw_thresh)

        # 估计剩余时间
        start_time = end_time
        end_time = time.time()
        time_stat.append(end_time - start_time)
        time_cost = np.mean(time_stat)
        eta_sec = (num_imgs - k) * time_cost
        eta = str(datetime.timedelta(seconds=int(eta_sec)))

        logger.info('Infer iter {}, num_imgs={}, eta={}.'.format(k, num_imgs, eta))
        if draw_image:
            t2 = threading.Thread(target=save_img, args=(filename, image))
            t2.start()
            logger.info("Detection bbox results save in images/res/{}".format(filename))
    cost = time.time() - start
    logger.info('total time: {0:.6f}s'.format(cost))
    logger.info('Speed: %.6fs per image,  %.1f FPS.'%((cost / num_imgs), (num_imgs / cost)))


