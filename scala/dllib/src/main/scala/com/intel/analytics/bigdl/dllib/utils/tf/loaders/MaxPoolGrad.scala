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
import com.intel.analytics.bigdl.dllib.nn.abstractnn.DataFormat
import com.intel.analytics.bigdl.dllib.nn.tf.{MaxPoolGrad => MaxPoolGradOps}
import com.intel.analytics.bigdl.dllib.tensor.TensorNumericMath.TensorNumeric
import com.intel.analytics.bigdl.dllib.utils.Log4Error
import com.intel.analytics.bigdl.dllib.utils.tf.Context
import org.tensorflow.framework.NodeDef

import scala.reflect.ClassTag

class MaxPoolGrad extends TensorflowOpsLoader {

  import Utils._

  override def build[T: ClassTag](nodeDef: NodeDef, byteOrder: ByteOrder,
    context: Context[T])(implicit ev: TensorNumeric[T]): Module[T] = {
    val attributes = nodeDef.getAttrMap
    val (pW, pH) =
      if (getString(attributes, "padding") == "SAME") {
        (-1, -1)
      } else {
        (0, 0)
      }
    val strideList = getIntList(attributes, "strides")
    Log4Error.invalidInputError(strideList.head == 1, s"not support strides on batch")
    val kernelSize = getIntList(attributes, "ksize")
    Log4Error.invalidInputError(kernelSize.head == 1, s"not support kernel on batch")

    val format = getString(attributes, "data_format")
    val poolgrad = format match {
      case "NHWC" =>
        Log4Error.invalidInputError(strideList(3) == 1, s"not support strides on depth")
        val strideW = strideList(1)
        val strideH = strideList(2)
        val kW = kernelSize(1)
        val kH = kernelSize(2)
        MaxPoolGradOps[T](kW, kH, strideW, strideH, pW, pH, DataFormat.NHWC)

      case "NCHW" =>
        Log4Error.invalidInputError(strideList(1) == 1, s"not support strides on depth")
        val strideW = strideList(2)
        val strideH = strideList(3)
        val kW = kernelSize(2)
        val kH = kernelSize(3)
        MaxPoolGradOps[T](kW, kH, strideW, strideH, pW, pH, DataFormat.NCHW)
      case _ =>
        throw new IllegalArgumentException(s"not supported data format: $format")
    }
    poolgrad.asInstanceOf[Module[T]]
  }
}
