/*
 * Copyright 2016 The BigDL Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.intel.analytics.bigdl.dllib.utils.tf.loaders

import java.nio.ByteOrder

import com.intel.analytics.bigdl.Module
import com.intel.analytics.bigdl.dllib.nn.abstractnn.{AbstractModule, Activity, DataFormat}
import com.intel.analytics.bigdl.dllib.nn.tf.{Conv3DBackpropFilterV2 => Conv3DBackpropFilterV2Ops}
import com.intel.analytics.bigdl.dllib.tensor.TensorNumericMath.TensorNumeric
import com.intel.analytics.bigdl.dllib.utils.Log4Error
import com.intel.analytics.bigdl.dllib.utils.tf.Context
import org.tensorflow.framework.NodeDef

import scala.reflect.ClassTag

class Conv3DBackpropFilterV2 extends TensorflowOpsLoader {

  import Utils._

  override def build[T: ClassTag](nodeDef: NodeDef, byteOrder: ByteOrder,
                                  context: Context[T])(implicit ev: TensorNumeric[T]): Module[T] = {
    val attributes = nodeDef.getAttrMap
    val (pT, pW, pH) =
      if (getString(attributes, "padding") == "SAME") {
        (-1, -1, -1)
      } else {
        (0, 0, 0)
      }
    val strideList = getIntList(attributes, "strides")
    Log4Error.invalidInputError(strideList.head == 1, s"not support strides on batch")

    val format = getString(attributes, "data_format")
    val conv = format match {
      case "NDHWC" =>
        Log4Error.invalidInputError(strideList(4) == 1, s"not support strides on depth")
        val dT = strideList(1)
        val dW = strideList(2)
        val dH = strideList(3)
        Conv3DBackpropFilterV2Ops[T](dT, dW, dH, pT, pW, pH, DataFormat.NHWC)
      case "NCDHW" =>
        Log4Error.invalidInputError(strideList(1) == 1, s"not support strides on depth")
        val dT = strideList(2)
        val dW = strideList(3)
        val dH = strideList(4)
        Conv3DBackpropFilterV2Ops[T](dT, dW, dH, pT, pW, pH, DataFormat.NCHW)
      case _ =>
        throw new IllegalArgumentException(s"not supported data format: $format")
    }
    conv.asInstanceOf[AbstractModule[Activity, Activity, T]]
  }
}
