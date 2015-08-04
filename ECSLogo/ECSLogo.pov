//  Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License").
// You may not use this file except in compliance with the License.
// A copy of the License is located at
//
//     http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file.
// This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and limitations under the License.

// The Amazon EC2 Container Service (ECS) Logo, powered by AWS.

// Includes.
#include "colors.inc"
#include "rad_def.inc"
#include "finish.inc"

// Global settings and defaults.
global_settings {
    radiosity {
        Rad_Settings(Radiosity_OutdoorHQ,off,off)
    }
}
#default {finish{ambient 0}}

// Declarations.
#declare ImageWidth = 1920;
#declare ImageHeight = 1080;

#declare AWSOrange = rgb <1, .5, 0>;

#declare PoweredByAWSLogoImageFile = "AWS_Logo_PoweredBy_300px.png"
#declare PoweredByAWSLogoImageWidth = 300;
#declare PoweredByAWSLogoImageHeight = 122;
#declare PoweredByAWSLogoAspect = PoweredByAWSLogoImageHeight / PoweredByAWSLogoImageWidth;

#declare PoweredByAWSLogoSize = 0.5;
#declare PoweredByAWSLogoDepth = .00001;
#declare PoweredByAWSLogoXPosition = 1.3;
#declare PoweredByAWSLogoYPosition = 0.8;

#declare ECSPlaneThickness = 0.1;
#declare ECSPlaneSpacing = ECSPlaneThickness * 2;
#declare ECSFrameInset = 3/5;
#declare ECSContainerSpacing = ECSFrameInset / 3;
#declare ECSContainerWidth = (ECSFrameInset - ECSContainerSpacing) / 2;
#declare ECSContainerHeight = ECSContainerWidth;
#declare ECSContainerLength = ECSContainerWidth * 2;
#declare ECSContainerXOffset = (ECSContainerWidth + ECSContainerSpacing) / 2;
#declare ECSContainerYOffset = (ECSContainerHeight + ECSContainerSpacing) / 2;
#declare ECSContainerZOffset = ECSContainerLength;

#declare ECSLogoTexture = texture {
    pigment {
        color AWSOrange
    }
}

#declare ECSFrame = difference {
    box {
        <-0.5,  0.5, -ECSPlaneThickness/2>,
        < 0.5, -0.5,  ECSPlaneThickness/2>
        texture {
            ECSLogoTexture
        }
    }
    box {
        <-ECSFrameInset/2,  ECSFrameInset/2, -ECSPlaneThickness>,
        < ECSFrameInset/2, -ECSFrameInset/2,  ECSPlaneThickness>
    }
    cutaway_textures
}

#declare ECSFrameExtra =  box {
    <-0.5,                      0.5, -ECSPlaneThickness/2>,
    <-0.5 + ECSFrameInset / 2, -0.5,  ECSPlaneThickness/2>
    texture {
        ECSLogoTexture
    }
}

#declare ECSContainer =  box {
    <-ECSContainerWidth/2,  ECSContainerHeight/2, -ECSContainerLength/2>,
    < ECSContainerWidth/2, -ECSContainerHeight/2,  ECSContainerLength/2>
    texture {
        ECSLogoTexture
    }
}

#declare ECSLogo = union {
    object {
        ECSFrameExtra
        translate <0, 0, ECSPlaneSpacing>
    }
    object {
        ECSFrame
    }
    object {  // top left container
        ECSContainer
        translate <-ECSContainerXOffset,  ECSContainerYOffset, -ECSContainerZOffset>
    }
    object {  // top right container
        ECSContainer
        translate < ECSContainerXOffset,  ECSContainerYOffset, -ECSContainerZOffset>
    }
    object {  // bottom left container
        ECSContainer
        translate <-ECSContainerXOffset, -ECSContainerYOffset, -ECSContainerZOffset>
    }
    object {  // bottom right container
        ECSContainer
        translate < ECSContainerXOffset, -ECSContainerYOffset, -ECSContainerZOffset>
    }
}

#declare PoweredByAWSLogo = box {
    <-0.5,  PoweredByAWSLogoAspect / 2, -PoweredByAWSLogoDepth>,
    < 0.5, -PoweredByAWSLogoAspect / 2,  PoweredByAWSLogoDepth>
    texture {
        pigment {
            color White
        }
        finish {
            ambient 0
            diffuse 1
        }
    }
    texture {
        pigment {
            image_map {
                png PoweredByAWSLogoImageFile
                map_type 0
            }
        }
        finish {
            ambient 0
            diffuse 1
        }
        translate <-0.5, -0.5, 0>
        scale <1, PoweredByAWSLogoAspect, 1>
    }
}

// The scene.

background { color White }

plane {
    y, -0.5
    texture {
        pigment {
            color White
        }
    }
    finish {
        Glossy
    }
}

object {
    ECSLogo
    rotate <0, -45, 0>
}

object {
    PoweredByAWSLogo
    scale PoweredByAWSLogoSize
    translate  <PoweredByAWSLogoXPosition, PoweredByAWSLogoYPosition, 0>
}

light_source {
    < 5, 10, -10>
    color White * 0.6
    area_light <5, 0, 0>, <0, 0, 5>, 5, 5
    adaptive 1
    jitter
}

camera {
    right x * ImageWidth/ImageHeight
    location <0, 0, -2>
    look_at  <0, 0,  0>
}
