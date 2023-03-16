import tkinter
from PIL import Image
import numpy as np
from scipy.sparse import csr_matrix
from pyamg.gallery import poisson
from pyamg import ruge_stuben_solver
import matplotlib.pyplot as plt
from skimage.draw import polygon
import scipy.sparse as sp
import cv2

laplacian_operator = np.array([[0, 1, 0],
                               [1, -4, 1],
                               [0, 1, 0]])
def getImagePathFromUser(msg):
    tkinter.Tk().withdraw()
    return tkinter.filedialog.askopenfilename(title=msg)


def rgbToGrayMat(imgPth):
    gryImg = Image.open(imgPth).convert('L')
    return np.asarray(gryImg)


def getImageFromUser(imgPth, srcShp=(0, 0)):
    # imgPth = getImagePathFromUser(msg)
    # imgPth =
    rgb = splitImageToRgb(imgPth)
    if not np.all(np.asarray(srcShp) < np.asarray(rgb[0].shape)):
        return getImageFromUser('Open destination image with resolution bigger than ' +
                                str(tuple(np.asarray(srcShp) + 1)), srcShp)
    return imgPth, rgb


def polyMask(imgPth, numOfPts=100):
    img = rgbToGrayMat(imgPth)
    plt.figure('source image')
    plt.title('Inscribe the region you would like to blend inside a polygon')
    plt.imshow(img, cmap='gray')
    pts = np.asarray(plt.ginput(numOfPts, timeout=1))
    plt.close('all')
    if len(pts) < 3:
        minRow, minCol = (0, 0)
        maxRow, maxCol = img.shape
        mask = np.ones(img.shape)
    else:
        pts = np.fliplr(pts)
        inPolyRow, inPolyCol = polygon(tuple(pts[:, 0]), tuple(pts[:, 1]), img.shape)
        minRow, minCol = (np.max(np.vstack([np.floor(np.min(pts, axis=0)).astype(int).reshape((1, 2)), (0, 0)]),
                                 axis=0))
        maxRow, maxCol = (np.min(np.vstack([np.ceil(np.max(pts, axis=0)).astype(int).reshape((1, 2)), img.shape]),
                                 axis=0))
        mask = np.zeros(img.shape)
        mask[inPolyRow, inPolyCol] = 1
        mask = mask[minRow: maxRow, minCol: maxCol]
    return mask, minRow, maxRow, minCol, maxCol


def splitImageToRgb(imgPth):
    r, g, b = Image.Image.split(Image.open(imgPth))
    return np.asarray(r), np.asarray(g), np.asarray(b)


def cropImageByLimits(src, minRow, maxRow, minCol, maxCol):
    r, g, b = src
    r = r[minRow: maxRow, minCol: maxCol]
    g = g[minRow: maxRow, minCol: maxCol]
    b = b[minRow: maxRow, minCol: maxCol]
    return r, g, b


def keepSrcInDstBoundaries(corner, gryDstShp, srcShp):
    for idx in range(len(corner)):
        if corner[idx] < 1:
            corner[idx] = 1
        if corner[idx] > gryDstShp[idx] - srcShp[idx] - 1:
            corner[idx] = gryDstShp[idx] - srcShp[idx] - 1
    return corner


def topLeftCornerOfSrcOnDst(dstImgPth, srcShp):
    gryDst = rgbToGrayMat(dstImgPth)
    plt.figure('destination image')
    plt.title('Where would you like to blend it..?')
    plt.imshow(gryDst, cmap='gray')
    center = np.asarray([]).astype(int)
    plt.close('all')
    if len(center) < 1:
        center = np.asarray([[gryDst.shape[1] // 2, gryDst.shape[0] // 2]]).astype(int)
    elif len(center) > 1:
        center = np.asarray([center[0]])
    corner = [center[0][1] - srcShp[0] // 2, center[0][0] - srcShp[1] // 2]
    return keepSrcInDstBoundaries(corner, gryDst.shape, srcShp)


def cropDstUnderSrc(dstImg, corner, srcShp):
    dstUnderSrc = dstImg[
                  corner[0]:corner[0] + srcShp[0],
                  corner[1]:corner[1] + srcShp[1]]
    return dstUnderSrc


    # return poisson(array.shape, format='csr') * csr_matrix(array.flatten()).transpose().toarray()
def laplacian(array):
    return cv2.filter2D(array.astype(np.float64), -1, laplacian_operator, borderType=cv2.BORDER_CONSTANT).reshape((-1,1))

    # return buildA(array.shape) * csr_matrix(array.flatten()).transpose().toarray()

def setBoundaryCondition(b, dstUnderSrc):
    b[1, :] = dstUnderSrc[1, :]
    b[-2, :] = dstUnderSrc[-2, :]
    b[:, 1] = dstUnderSrc[:, 1]
    b[:, -2] = dstUnderSrc[:, -2]
    b = b[1:-1, 1: -1]
    return b



def constructConstVector(mask, mixedGrad, dstUnderSrc, srcLaplacianed, srcShp):
    dstLaplacianed = laplacian(dstUnderSrc)
    b = np.reshape(mask * np.reshape(srcLaplacianed, srcShp) +
                   (1 - mask) * np.reshape(dstLaplacianed, srcShp), srcShp)

    return setBoundaryCondition(b, -dstUnderSrc.astype(np.float64))


def fixCoeffUnderBoundaryCondition(coeff, shape):
    shapeProd = np.prod(np.asarray(shape))
    arangeSpace = np.arange(shapeProd).reshape(shape)
    arangeSpace[1:-1, 1:-1] = -1
    indexToChange = arangeSpace[arangeSpace > -1]
    for j in indexToChange:
        coeff[j, j] = 1
        if j - 1 > -1:
            coeff[j, j - 1] = 0
        if j + 1 < shapeProd:
            coeff[j, j + 1] = 0
        if j - shape[-1] > - 1:
            coeff[j, j - shape[-1]] = 0
        if j + shape[-1] < shapeProd:
            coeff[j, j + shape[-1]] = 0
    return coeff


def constructCoefficientMat(shape):
    a = poisson(shape, format='lil')
    # a = fixCoeffUnderBoundaryCondition(a, shape)
    return a

def buildA(im_shape):
    sizey, sizex = im_shape
    A = sp.eye(sizex * sizey, format="csr")
    A = A * -4.
    A = A + sp.eye(sizex * sizey, k=1) + sp.eye(sizex * sizey, k=-1)
    A = A + sp.eye(sizex * sizey, k=-sizex) + sp.eye(sizex * sizey, k=sizex)
    for i in range(sizey * sizex):
        if (i % sizex) is (sizex -1) and (i+1 < sizey * sizex):
            A[i,i+1] = 0
            A[i+1, i] = 0
    return A


def buildLinearSystem(mask, srcImg, dstUnderSrc, mixedGrad):
    srcLaplacianed = laplacian(srcImg)
    b = constructConstVector(mask, mixedGrad, dstUnderSrc, srcLaplacianed, srcImg.shape)

    #a1 = constructCoefficientMat(b.shape)
    a = buildA(b.shape)
    return a, b


def solveLinearSystem(a, b, bShape):
    # multiLevel = ruge_stuben_solver(csr_matrix(a))

    # x = np.reshape((multiLevel.solve(b.flatten(), tol=1e-10)), bShape)
    x = np.reshape(sp.linalg.cgs(a, b.flatten())[0], bShape)
    # this code should be included
    x[x < 0] = 0
    x[x > 255] = 255
    return x


def blend(dst, patch, corner, patchShape, blended):
    mixed = dst.copy()
    mixed[corner[0]:corner[0] + patchShape[0], corner[1]:corner[1] + patchShape[1]] = patch
    blended.append(Image.fromarray(mixed))
    return blended


def poissonAndNaiveBlending(mask, corner, srcRgb, dstRgb, mixedGrad):
    poissonBlended = []
    naiveBlended = []
    for color in range(3):
        src = srcRgb[color]
        dst = dstRgb[color]
        dstUnderSrc = cropDstUnderSrc(dst, corner, src.shape)
        plt.figure('dstUnderSrc image')
        plt.title('dstUnderSrc')
        plt.imshow(dstUnderSrc, cmap='gray')
        plt.show()

        a, b = buildLinearSystem(mask, src, dstUnderSrc, mixedGrad)
        x = solveLinearSystem(a, b, b.shape)
        poissonBlended = blend(dst, x, (corner[0] + 1, corner[1] + 1), b.shape, poissonBlended)
        cropSrc = mask * src + (1 - mask) * dstUnderSrc
        naiveBlended = blend(dst, cropSrc, corner, src.shape, naiveBlended)
    return poissonBlended, naiveBlended


def mergeSaveShow(splitImg, ImgTtl):
    merged = Image.merge('RGB', tuple(splitImg))
    merged.save(ImgTtl + '.png')
    merged.show(ImgTtl)


def main():
    srcImgPth, srcRgb = getImageFromUser('./source_small.png')
    mask, *maskLimits = polyMask(srcImgPth)
    srcRgbCropped = cropImageByLimits(srcRgb, *maskLimits)
    dstImgPth, dstRgb = getImageFromUser('./target.jpg', srcRgbCropped[0].shape)
    corner = topLeftCornerOfSrcOnDst(dstImgPth, srcRgbCropped[0].shape)
    poissonBlended, naiveBlended = poissonAndNaiveBlending(mask, corner, srcRgbCropped, dstRgb, 0.)
    mergeSaveShow(naiveBlended, 'Naive Blended')
    mergeSaveShow(poissonBlended, 'Poisson Blended')


if __name__ == '__main__':
    main()
