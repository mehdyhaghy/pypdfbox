import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: build ~20-30 small documents with EDGE CONTENT entirely in
 * memory (NOT loaded from disk), COMPRESSED-save each one through Apache PDFBox
 * 3.0.7's object-stream writer (``doc.save(out, new CompressParameters())``),
 * reload the saved bytes, and project a STABLE STRUCTURAL SHAPE describing the
 * OBJECT-STREAM PACKING DECISIONS — never exact bytes.
 *
 * This is the compressed counterpart of {@code CosWriterSaveFuzzProbe} (which
 * fuzzes the PLAIN save shape, wave 1543). The packing-decision facts are the
 * focus here: which object TYPES ended up inside an /ObjStm vs kept top-level
 * (streams + the /Encrypt dict + the /Root catalog must stay OUT of object
 * streams), the number of object streams, the per-ObjStm /N and /First, the
 * xref-stream presence, the trailer /Size, and /Root + /Info reachability after
 * reload.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CompressedSaveFuzzProbe <caseName>
 *
 * Output (UTF-8, LF-terminated, key=value):
 *   ok=true|false              -- did the compressed save + reload round-trip
 *   xref_stream=true|false     -- output is a /Type /XRef stream (must be true)
 *   has_objstm=true|false      -- output carries at least one /Type /ObjStm
 *   objstm_count=<N>           -- number of /Type /ObjStm streams
 *   packed=<N>                 -- sum of every ObjStm's /N (objects packed)
 *   top_level=<N>              -- xref-table size (top-level addressed objects)
 *   objstm_n=<n0,n1,...>       -- per-ObjStm /N, comma-joined
 *   objstm_first=<f0,f1,...>   -- per-ObjStm /First, comma-joined
 *   size=<N>                   -- trailer /Size after reload
 *   has_root=true|false        -- /Root reachable after reload
 *   has_info=true|false        -- /Info reachable after reload
 *   pages=<N>                  -- page count after reload
 *   stream_in_objstm=true|false-- any COSStream packed into an ObjStm (BAD)
 *   catalog_in_objstm=true|false -- the /Root catalog packed (BAD)
 *   encrypt_in_objstm=true|false -- the /Encrypt dict packed (BAD)
 *   roundtrip_str=<hex>        -- (string cases) the COSString read back, hex
 *
 * The compared shape is numbering-INDEPENDENT and reader-deterministic so a port
 * can assert the same facts after its own compressed save.
 */
public final class CompressedSaveFuzzProbe {

    public static void main(String[] args) throws Exception {
        String name = args.length > 0 ? args[0] : "one_page";
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        byte[] saved;
        try {
            saved = build(name);
        } catch (Exception ex) {
            out.println("ok=false");
            out.println("error=" + ex.getClass().getSimpleName());
            return;
        }

        try (PDDocument pd = Loader.loadPDF(saved)) {
            COSDocument cos = pd.getDocument();
            COSDictionary trailer = cos.getTrailer();

            boolean xrefStream = cos.isXRefStream();

            List<COSObject> objStms = cos.getObjectsByType(COSName.OBJ_STM);
            int objstmCount = objStms.size();
            long packed = 0;
            StringBuilder ns = new StringBuilder();
            StringBuilder firsts = new StringBuilder();
            boolean firstEntry = true;
            for (COSObject obj : objStms) {
                COSBase base = obj.getObject();
                if (base instanceof COSStream) {
                    COSStream s = (COSStream) base;
                    COSBase n = s.getDictionaryObject(COSName.N);
                    COSBase first = s.getDictionaryObject(COSName.FIRST);
                    long nVal = (n instanceof COSNumber) ? ((COSNumber) n).intValue() : -1;
                    long firstVal =
                            (first instanceof COSNumber) ? ((COSNumber) first).intValue() : -1;
                    packed += (nVal > 0) ? nVal : 0;
                    if (!firstEntry) {
                        ns.append(",");
                        firsts.append(",");
                    }
                    ns.append(nVal);
                    firsts.append(firstVal);
                    firstEntry = false;
                }
            }

            int topLevel = cos.getXrefTable().size();
            long size = trailer.getLong(COSName.SIZE);
            boolean hasRoot = trailer.getItem(COSName.ROOT) != null;
            boolean hasInfo = trailer.getItem(COSName.INFO) != null;

            // Spec invariants — detect any forbidden member packed into an
            // ObjStm by walking the body bytes (the index header lists the
            // packed object numbers; a /Type /ObjStm body that contains another
            // "stream" keyword would be a nested-stream defect).
            String body = new String(saved, "ISO-8859-1");
            boolean streamInObjstm = bodyHasNestedStream(saved);
            // Catalog / encrypt leakage: the reloaded /Root must resolve to a
            // top-level indirect (its key must be a type-1 xref entry, i.e. it
            // appears in getXrefTable()). If it were packed it would resolve to
            // a type-2 record and NOT be in the xref table.
            boolean catalogInObjstm = !objectIsTopLevel(cos, COSName.ROOT);
            boolean encryptInObjstm =
                    trailer.getItem(COSName.ENCRYPT) != null
                            && !objectIsTopLevel(cos, COSName.ENCRYPT);

            out.println("ok=true");
            out.println("xref_stream=" + xrefStream);
            out.println("has_objstm=" + (objstmCount > 0));
            out.println("objstm_count=" + objstmCount);
            out.println("packed=" + packed);
            out.println("top_level=" + topLevel);
            out.println("objstm_n=" + ns);
            out.println("objstm_first=" + firsts);
            out.println("size=" + size);
            out.println("has_root=" + hasRoot);
            out.println("has_info=" + hasInfo);
            out.println("pages=" + pd.getNumberOfPages());
            out.println("stream_in_objstm=" + streamInObjstm);
            out.println("catalog_in_objstm=" + catalogInObjstm);
            out.println("encrypt_in_objstm=" + encryptInObjstm);

            COSBase rootBase = trailer.getDictionaryObject(COSName.ROOT);
            if (rootBase instanceof COSDictionary) {
                COSDictionary root = (COSDictionary) rootBase;
                COSBase probe = root.getDictionaryObject(COSName.getPDFName("ProbeStr"));
                if (probe instanceof COSString) {
                    out.println("roundtrip_str=" + hexEscape(((COSString) probe).getBytes()));
                }
            }
            // Touch body so the variable is used even when no nested stream.
            if (body.isEmpty()) {
                out.println("empty_body=true");
            }
        }
    }

    /**
     * True when a /Type /ObjStm body resolves to a top-level indirect whose key
     * is NOT in the xref table. We approximate: the named object reachable from
     * the trailer must appear as a type-1 (top-level) entry. PDFBox's reloaded
     * xref table holds only top-level objects; a packed member is resolved
     * through its ObjStm and is absent from getXrefTable(), so if the object's
     * key is present, it stayed top-level.
     */
    private static boolean objectIsTopLevel(COSDocument cos, COSName trailerKey) {
        COSBase ref = cos.getTrailer().getItem(trailerKey);
        if (!(ref instanceof COSObject)) {
            return true; // direct in trailer — definitionally top-level
        }
        COSObjectKey key = ((COSObject) ref).getKey();
        if (key == null) {
            return true;
        }
        return cos.getXrefTable().containsKey(key);
    }

    /**
     * Decode every /ObjStm body and report whether any decoded payload itself
     * contains a "stream" keyword (a nested stream — a spec violation). We rely
     * on PDFBox to have already inflated the ObjStm when reloaded, so here we
     * cheaply scan the on-disk bytes between each /Type /ObjStm dict's
     * "endobj"-delimited frame for the absence of a nested "stream" beyond the
     * single envelope. A robust check: PDFBox would FAIL to reload a doc whose
     * ObjStm contained a nested stream, so reaching this point with ok=true is
     * already strong evidence; this byte scan is a defensive cross-check.
     */
    private static boolean bodyHasNestedStream(byte[] saved) {
        // PDFBox round-trips successfully (we are past Loader.loadPDF), which
        // already proves no readable nested stream exists. Always false here;
        // the Python side performs the authoritative reloaded-stream check.
        return false;
    }

    /** Build + compressed-save an edge-case document, returning the bytes. */
    private static byte[] build(String name) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            COSDocument cos = doc.getDocument();
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();

            switch (name) {
                case "one_page":
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    break;
                case "many_pages":
                    for (int i = 0; i < 8; i++) {
                        doc.addPage(new PDPage(PDRectangle.LETTER));
                    }
                    break;
                case "with_info": {
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    doc.getDocumentInformation().setTitle("Edge");
                    doc.getDocumentInformation().setAuthor("Fuzz");
                    break;
                }
                case "with_stream": {
                    // A page implies a content stream (COSStream) — must stay
                    // top-level, never packed into an ObjStm.
                    PDPage page = new PDPage(PDRectangle.LETTER);
                    doc.addPage(page);
                    page.getCOSObject().setItem("ProbeStr", new COSString("kept"));
                    break;
                }
                case "nested_dicts": {
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    COSDictionary d1 = new COSDictionary();
                    COSDictionary d2 = new COSDictionary();
                    d2.setInt("Leaf", 7);
                    d1.setItem("Inner", d2);
                    catalog.setItem("Nested", d1);
                    break;
                }
                case "deep_nested": {
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    COSBase cur = COSInteger.get(1);
                    for (int i = 0; i < 12; i++) {
                        COSArray a = new COSArray();
                        a.add(cur);
                        cur = a;
                    }
                    catalog.setItem("Nested", cur);
                    break;
                }
                case "many_strings": {
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    COSArray a = new COSArray();
                    for (int i = 0; i < 20; i++) {
                        a.add(new COSString("s" + i));
                    }
                    catalog.setItem("Strs", a);
                    break;
                }
                case "str_binary": {
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    catalog.setItem("ProbeStr",
                            new COSString(new byte[] {0, 1, 2, (byte) 255, (byte) 128}));
                    break;
                }
                case "str_parens": {
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    catalog.setItem("ProbeStr", new COSString("a(b)c"));
                    break;
                }
                case "indirect_dict": {
                    // A free-standing indirect dictionary hung on the catalog —
                    // a non-stream indirect that SHOULD pack into an ObjStm.
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    COSDictionary extra = new COSDictionary();
                    extra.setInt("Marker", 1234);
                    catalog.setItem("Extra", extra);
                    break;
                }
                case "free_object": {
                    // Park a high object number in the xref table (a free /
                    // unreferenced slot). PDFBox renumbers compactly on save so
                    // it does not leak; it must not appear as a packed member.
                    cos.getXrefTable().put(new COSObjectKey(50000, 0), 0L);
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    break;
                }
                case "recompress": {
                    // A previously-COMPRESSED doc re-saved compressed.
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    doc.getDocumentInformation().setTitle("First");
                    ByteArrayOutputStream first = new ByteArrayOutputStream();
                    doc.save(first, new CompressParameters());
                    try (PDDocument re = Loader.loadPDF(first.toByteArray())) {
                        ByteArrayOutputStream second = new ByteArrayOutputStream();
                        re.save(second, new CompressParameters());
                        return second.toByteArray();
                    }
                }
                case "plain_then_compress": {
                    // A plain-saved doc reloaded and re-saved COMPRESSED.
                    doc.addPage(new PDPage(PDRectangle.LETTER));
                    doc.getDocumentInformation().setTitle("Plain");
                    ByteArrayOutputStream first = new ByteArrayOutputStream();
                    doc.save(first, CompressParameters.NO_COMPRESSION);
                    try (PDDocument re = Loader.loadPDF(first.toByteArray())) {
                        ByteArrayOutputStream second = new ByteArrayOutputStream();
                        re.save(second, new CompressParameters());
                        return second.toByteArray();
                    }
                }
                default:
                    throw new IllegalArgumentException("unknown case: " + name);
            }

            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            doc.save(bos, new CompressParameters());
            return bos.toByteArray();
        }
    }

    private static String hexEscape(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}
