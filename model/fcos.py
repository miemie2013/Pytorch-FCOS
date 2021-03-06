#! /usr/bin/env python
# coding=utf-8
# ================================================================
#
#   Author      : miemie2013
#   Created date: 2020-08-21 19:33:37
#   Description : pytorch_fcos
#
# ================================================================
import torch

class FCOS(torch.nn.Module):
    def __init__(self, backbone, neck, head):
        super(FCOS, self).__init__()
        self.backbone = backbone
        self.neck = neck
        self.head = head

    def forward(self, x, im_info, eval=True, tag_labels=None, tag_bboxes=None, tag_centerness=None):
        body_feats = self.backbone(x)
        body_feats, spatial_scale = self.neck(body_feats)
        if eval:
            out = self.head.get_prediction(body_feats, im_info)
        else:
            out = self.head.get_loss(body_feats, tag_labels, tag_bboxes, tag_centerness)
        return out




