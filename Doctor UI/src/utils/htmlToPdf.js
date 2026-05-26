import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

/**
 * Capture a DOM element and generate a multi-page PDF that preserves
 * the on-screen clinical-document layout (Format A).
 *
 * @param {HTMLElement} element - The DOM node to capture (e.g. `.paper`)
 * @param {Object}      opts
 * @param {string}     [opts.fileName]  - Download file name (omit to get a Blob)
 * @param {boolean}    [opts.download]  - true → trigger browser download
 * @returns {Promise<Blob>} The generated PDF as a Blob
 */
export async function generatePdfFromElement(element, { fileName, download = false } = {}) {
  if (!element) throw new Error('generatePdfFromElement: element is required');

  // ── snapshot the element via html2canvas ──────────────────────────
  const canvas = await html2canvas(element, {
    scale: 2,                // 2× for sharp text on retina / print
    useCORS: true,
    logging: false,
    backgroundColor: '#ffffff',
    // Expand the canvas height to capture the full scrollable content
    windowHeight: element.scrollHeight,
  });

  const imgData = canvas.toDataURL('image/png');
  const imgW    = canvas.width;
  const imgH    = canvas.height;

  // ── build the PDF ────────────────────────────────────────────────
  // A4 dimensions in mm
  const pdfW = 210;
  const pdfH = 297;
  const margin = 10; // mm margin on each side

  const contentW = pdfW - margin * 2;
  const contentH = pdfH - margin * 2;

  // Scale factor: map image px → PDF mm
  const ratio   = contentW / imgW;
  const scaledH = imgH * ratio; // total image height in PDF mm

  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  let yOffset = 0;      // how much of the image we've placed (in px)
  let page    = 0;

  while (yOffset < imgH) {
    if (page > 0) doc.addPage();

    // Height of this page's slice (in image px)
    const sliceH = Math.min(contentH / ratio, imgH - yOffset);

    // Create a temporary canvas for just this page's slice
    const pageCanvas = document.createElement('canvas');
    pageCanvas.width  = imgW;
    pageCanvas.height = Math.ceil(sliceH);
    const ctx = pageCanvas.getContext('2d');
    ctx.drawImage(
      canvas,
      0, yOffset,           // source x, y
      imgW, sliceH,         // source w, h
      0, 0,                 // dest x, y
      imgW, sliceH,         // dest w, h
    );

    const pageImgData = pageCanvas.toDataURL('image/png');
    doc.addImage(pageImgData, 'PNG', margin, margin, contentW, sliceH * ratio);

    // Page footer
    doc.setFontSize(8);
    doc.setTextColor(150, 150, 150);
    doc.text(
      `Page ${page + 1} | ClearPath Clinical Care Plan | ${new Date().toLocaleDateString()}`,
      pdfW / 2, pdfH - 5,
      { align: 'center' },
    );

    yOffset += sliceH;
    page++;
  }

  // ── output ───────────────────────────────────────────────────────
  const blob = doc.output('blob');

  if (download && fileName) {
    doc.save(fileName);
  }

  return blob;
}
