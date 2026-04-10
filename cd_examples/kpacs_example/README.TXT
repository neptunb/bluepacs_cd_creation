COMMERCIAL DISTRIBUTION PROHIBITED WITHOUT PERMISSION

By installing or using the K-PACS software you consent to be bound by this agreement. If you do not agree to all of the terms of this agreement, you must not install or use the software.

The software is provided as is without warranty of any kind. The entire risk as to the quality and performance of the software is borne by you. No use of the software is authorized except under this disclaimer. The author will not be held liable for any damages whatsoever arising from the use of the software.

This software is for scientific use only. To prevent any harm from patients your are not supposed to use this software in healt care.

The software is protected by copyright and other intellectual property laws and by international treaties.


------------------------------


Minimum requirements:

· Intel Pentium III 800-MHz processor
· Windows 2000/XP/NT 4 or later
· 256MB of available RAM
· 50 MB of available disk space
· Monitor Resolution 1024x768 pixel
· Mouse


Recommended:

· Intel Pentium IV/Athlon XP 2000MHz (or more) processor
· Windows 2000/XP or later
· 512MB of available RAM
· lots of MB of available disk space
· Monitor resolution 1280x1024 pixel (or more)
· Wheelmouse

------------------------------


TO INSTALL K-PACS on a Windows computer:

1. Run KPSetup.exe from hier.
2. Follow the on-screen instructions
3. Launch K-Pacs by selecting it from the Start Menu or Desktop


------------------------------


The author provides limited technical support through email. I will do my best to answer your questions thoroughly and in a timely manner. I am also interested in your ideas concerning new features or functions. Please send your email to Andreas@k-pacs.de


------------------------------


Andreas Knopke
author





------------------------------

K-Pacs utilizes a modified version of the ezDICOMax plugin by Chris Rorden.


ezDICOM medical viewer 
Copyright (c) 2002, Wolfgang Krug and Chris Rorden
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
Neither the names of the copyright owners nor the names of this project (ezDICOM) may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.



--------------------------------
For Dicom connectivity K-PACS uses the DCMTK from Offis
Read their licence:


COPYRIGHT

Unless otherwise specified, the DCMTK software package has the
following copyright:

/*
 *  Copyright (C) 1994-2004, OFFIS
 *
 *  This software and supporting documentation were developed by
 *
 *    Kuratorium OFFIS e.V.
 *    Healthcare Information and Communication Systems
 *    Escherweg 2
 *    D-26121 Oldenburg, Germany
 *
 *  THIS SOFTWARE IS MADE AVAILABLE,  AS IS,  AND OFFIS MAKES NO  WARRANTY
 *  REGARDING  THE  SOFTWARE,  ITS  PERFORMANCE,  ITS  MERCHANTABILITY  OR
 *  FITNESS FOR ANY PARTICULAR USE, FREEDOM FROM ANY COMPUTER DISEASES  OR
 *  ITS CONFORMITY TO ANY SPECIFICATION. THE ENTIRE RISK AS TO QUALITY AND
 *  PERFORMANCE OF THE SOFTWARE IS WITH THE USER.
 *
 *  Copyright of the software  and  supporting  documentation  is,  unless
 *  otherwise stated, owned by OFFIS, and free access is hereby granted as
 *  a license to  use  this  software,  copy  this  software  and  prepare
 *  derivative works based upon this software.  However, any  distribution
 *  of this software source code or supporting documentation or derivative
 *  works  (source code and  supporting documentation)  must  include  the
 *  three paragraphs of this copyright notice.
 *
 */

Some portions of the DCMTK software package are derived from earlier
versions of this software with the following copyright, and can be
identifed by the following copyright notice located in each source file:

/*
 *  Copyright (C) 1993/1994, OFFIS, Oldenburg University and CERIUM
 *
 *  This software and supporting documentation were
 *  developed by
 *
 *    Institut OFFIS
 *    Bereich Kommunikationssysteme
 *    Westerstr. 10-12
 *    26121 Oldenburg, Germany
 *
 *    Fachbereich Informatik
 *    Abteilung Prozessinformatik
 *    Carl von Ossietzky Universitaet Oldenburg
 *    Ammerlaender Heerstr. 114-118
 *    26111 Oldenburg, Germany
 *
 *    CERIUM
 *    Laboratoire SIM
 *    Faculte de Medecine
 *    2 Avenue du Pr. Leon Bernard
 *    35043 Rennes Cedex, France
 *
 *  for CEN/TC251/WG4 as a contribution to the Radiological
 *  Society of North America (RSNA) 1993 Digital Imaging and
 *  Communications in Medicine (DICOM) Demonstration.
 *
 *  THIS SOFTWARE IS MADE AVAILABLE, AS IS, AND NEITHER OFFIS,
 *  OLDENBURG UNIVERSITY NOR CERIUM MAKE ANY WARRANTY REGARDING
 *  THE SOFTWARE, ITS PERFORMANCE, ITS MERCHANTABILITY OR
 *  FITNESS FOR ANY PARTICULAR USE, FREEDOM FROM ANY COMPUTER
 *  DISEASES OR ITS CONFORMITY TO ANY SPECIFICATION.  THE
 *  ENTIRE RISK AS TO QUALITY AND PERFORMANCE OF THE SOFTWARE
 *  IS WITH THE USER.
 *
 *  Copyright of the software and supporting documentation
 *  is, unless otherwise stated, jointly owned by OFFIS,
 *  Oldenburg University and CERIUM and free access is hereby
 *  granted as a license to use this software, copy this
 *  software and prepare derivative works based upon this
 *  software. However, any distribution of this software
 *  source code or supporting documentation or derivative
 *  works (source code and supporting documentation) must
 *  include the three paragraphs of this copyright notice.
 *
 */

Some other parts of this software within the dcmtk/dcmnet
sub-package related to the DICOM Upper Layer Protocol are
derived from software developed for the RSNA'93 DICOM
demonstration and kindly made available to us by the Mallinckrodt
Institute of Radiology.  Such software can be identifed by the
following copyright notice located in each affected source file:

/*
 *  Copyright (C) 1993, RSNA and Washington University
 *
 *  The software and supporting documentation for the Radiological
 *  Society of North America (RSNA) 1993 Digital Imaging and
 *  Communications in Medicine (DICOM) Demonstration were developed
 *  at the
 *          Electronic Radiology Laboratory
 *          Mallinckrodt Institute of Radiology
 *          Washington University School of Medicine
 *          510 S. Kingshighway Blvd.
 *          St. Louis, MO 63110
 *  as part of the 1993 DICOM Central Test Node project for, and
 *  under contract with, the Radiological Society of North America.
 *
 *  THIS SOFTWARE IS MADE AVAILABLE, AS IS, AND NEITHER RSNA NOR
 *  WASHINGTON UNIVERSITY MAKE ANY WARRANTY ABOUT THE SOFTWARE, ITS
 *  PERFORMANCE, ITS MERCHANTABILITY OR FITNESS FOR ANY PARTICULAR
 *  USE, FREEDOM FROM ANY COMPUTER DISEASES OR ITS CONFORMITY TO ANY
 *  SPECIFICATION. THE ENTIRE RISK AS TO QUALITY AND PERFORMANCE OF
 *  THE SOFTWARE IS WITH THE USER.
 *
 *  Copyright of the software and supporting documentation is
 *  jointly owned by RSNA and Washington University, and free access
 *  is hereby granted as a license to use this software, copy this
 *  software and prepare derivative works based upon this software.
 *  However, any distribution of this software source code or
 *  supporting documentation or derivative works (source code and
 *  supporting documentation) must include the three paragraphs of
 *  the copyright notice.
 */

The dcmjpeg sub-package includes an adapted version of the Independent JPEG
Group Toolkit Version 6b, which is contained in dcmjpeg/libijg8,
dcmjpeg/libijg12 and dcmjpeg/libijg16.  This toolkit is covered by the
following copyright.  The original README file for the Independent JPEG
Group Toolkit is located in dcmjpeg/docs/ijg_readme.txt.

/*
 *  The authors make NO WARRANTY or representation, either express or implied,
 *  with respect to this software, its quality, accuracy, merchantability, or
 *  fitness for a particular purpose.  This software is provided "AS IS", and you,
 *  its user, assume the entire risk as to its quality and accuracy.
 *
 *  This software is copyright (C) 1991-1998, Thomas G. Lane.
 *  All Rights Reserved except as specified below.
 *
 *  Permission is hereby granted to use, copy, modify, and distribute this
 *  software (or portions thereof) for any purpose, without fee, subject to these
 *  conditions:
 *  (1) If any part of the source code for this software is distributed, then this
 *  README file must be included, with this copyright and no-warranty notice
 *  unaltered; and any additions, deletions, or changes to the original files
 *  must be clearly indicated in accompanying documentation.
 *  (2) If only executable code is distributed, then the accompanying
 *  documentation must state that "this software is based in part on the work of
 *  the Independent JPEG Group".
 *  (3) Permission for use of this software is granted only if the user accepts
 *  full responsibility for any undesirable consequences; the authors accept
 *  NO LIABILITY for damages of any kind.
 *
 *  These conditions apply to any software derived from or based on the IJG code,
 *  not just to the unmodified library.  If you use our work, you ought to
 *  acknowledge us.
 *
 *  Permission is NOT granted for the use of any IJG author's name or company name
 *  in advertising or publicity relating to this software or products derived from
 *  it.  This software may be referred to only as "the Independent JPEG Group's
 *  software".
 *
 *  We specifically permit and encourage the use of this software as the basis of
 *  commercial products, provided that all warranty or liability claims are
 *  assumed by the product vendor.
 */


The color quantization code in module dcmimage (dcmquant and the related
classes) is derived from code written by Jef Poskanzer for the NetPBM
toolkit which has the following copyright:

/*
 * Copyright (C) 1989, 1991 by Jef Poskanzer.
 *
 * Permission to use, copy, modify, and distribute this software and its
 * documentation for any purpose and without fee is hereby granted, provided
 * that the above copyright notice appear in all copies and that both that
 * copyright notice and this permission notice appear in supporting
 * documentation.  This software is provided "as is" without express or
 * implied warranty.
 */


The code for the OFStandard::strlcpy and OFStandard::strlcat helper
functions in ofstd/libsrc/ofstd.cc has been derived from the BSD
implementation of strlcpy() and strlcat() and which carries the
following copyright notice:

/*
 *  Copyright (c) 1998 Todd C. Miller <Todd.Miller(at)courtesan.com>
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions
 *  are met:
 *  1. Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *  2. Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in the
 *     documentation and/or other materials provided with the distribution.
 *  3. The name of the author may not be used to endorse or promote products
 *     derived from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
 *  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
 *  AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL
 *  THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 *  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 *  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 *  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 *  WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 *  OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
 *  ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */


The code for the OFStandard::atof helper function in
ofstd/libsrc/ofstd.cc has been derived from an implementation which
carries the following copyright notice:

/*
 *  Copyright 1988 Regents of the University of California
 *  Permission to use, copy, modify, and distribute this software and
 *  its documentation for any purpose and without fee is hereby granted,
 *  provided that the above copyright notice appear in all copies.  The
 *  University of California makes no representations about the
 *  suitability of this software for any purpose.  It is provided "as
 *  is" without express or implied warranty.
 *
 *
 *  The code for OFStandard::ftoa has been derived
 *  from an implementation which carries the following copyright notice:
 *
 *  Copyright (c) 1988 Regents of the University of California.
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms are permitted
 *  provided that the above copyright notice and this paragraph are
 *  duplicated in all such forms and that any documentation,
 *  advertising materials, and other materials related to such
 *  distribution and use acknowledge that the software was developed
 *  by the University of California, Berkeley.  The name of the
 *  University may not be used to endorse or promote products derived
 *  from this software without specific prior written permission.
 *  THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY EXPRESS OR
 *  IMPLIED WARRANTIES, INCLUDING, WITHOUT LIMITATION, THE IMPLIED
 *  WARRANTIES OF MERCHANTIBILITY AND FITNESS FOR A PARTICULAR PURPOSE.
 */

The "Base64" encoder/decoder in ofstd/libsrc/ofstd.cc has been derived
from an implementation which carries the following copyright notice:

/*
 *  Copyright (c) 1999, Bob Withers - bwit(at)pobox.com
 *
 *  This code may be freely used for any purpose, either personal or commercial,
 *  provided the authors copyright notice remains intact.
 */
--------------------------------
Some DICOM network services are implemented with the DICOMDLL library by R. Sanguinetti from Charrua Software
see http://www.charrua.com/vista for details. The DICOMDLL library is derived from Mark Oskin's UCDMC99 library


Copyright (C) 1995, University of California, Davis

THIS SOFTWARE IS MADE AVAILABLE, AS IS, AND THE UNIVERSITY
OF CALIFORNIA DOES NOT MAKE ANY WARRANTY ABOUT THE SOFTWARE, ITS PERFORMANCE, ITS MERCHANTABILITY OR FITNESS FOR ANY PARTICULAR USE, FREEDOM FROM ANY COMPUTER DISEASES OR ITS CONFORMITY TO ANY SPECIFICATION. THE ENTIRE RISK AS TO QUALITY AND PERFORMANCE OF THE SOFTWARE IS WITH THE USER.
Copyright of the software and supporting documentation is
owned by the University of California, and free access
is hereby granted as a license to use this software, copy this
software and prepare derivative works based upon this software. However, any distribution of this software source code or supporting documentation or derivative works (source code and supporting documentation) must include this copyright notice.
--------------------------------
For JPEG convertion K-PACS uses the Jpeg2dcm Software by R. Sanguinetti from Charrua Software
see http://www.charrua.com/vista for details

--------------------------------

For TWAIN device support the freeware library DelphiTwain by Gustavo Daud  is used. 

--------------------------------



