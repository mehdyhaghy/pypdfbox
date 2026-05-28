import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDestinationNameTreeNode;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitHeightDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitRectangleDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitWidthDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination;

/**
 * Live oracle probe: emit a CANONICAL, deterministic JSON listing of every
 * explicit page destination reachable from a PDF's catalog, decoded by Apache
 * PDFBox.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> DestinationTypesProbe input.pdf
 *
 * The probe walks two surfaces and merges their entries into one sorted JSON
 * array:
 *   1) the catalog's modern /Names /Dests name tree (string keys);
 *   2) the catalog's legacy /Dests flat dictionary (name keys).
 *
 * Each entry is a JSON object with the following fields:
 *
 *   surface     "tree" (from /Names /Dests) or "dests" (legacy /Dests)
 *   key         the destination name (sort key)
 *   dest_type   the upstream Java simple class name returned by
 *               PDDestination.create() for that array — XYZ/Fit/FitH/FitV/FitR
 *               all map to dedicated wrapper classes (PDPageXYZDestination,
 *               PDPageFitDestination, PDPageFitWidthDestination,
 *               PDPageFitHeightDestination, PDPageFitRectangleDestination)
 *               while FitB/FitBH/FitBV reuse the non-bounded wrapper classes
 *               in upstream — this field pins that exact collapse.
 *   type_name   the array's /D[1] type-name string (XYZ / Fit / FitB / FitH /
 *               FitBH / FitV / FitBV / FitR) — the behaviourally-meaningful
 *               identity independent of which Java wrapper a given language
 *               binding picks.
 *   page_index  the 0-based page index resolved via
 *               PDPageDestination.retrievePageNumber()
 *   left/top/right/bottom/zoom
 *               the upstream coordinate getters appropriate to the concrete
 *               class — written as JSON numbers; absent slots emit a JSON
 *               null (NOT the Java -1 sentinel) so each accessor's
 *               "retain current viewer value" semantics survives the
 *               language boundary. Accessors that do not exist on the
 *               concrete class (e.g. getZoom on PDPageFitDestination) emit
 *               null too.
 *
 * Output is a single JSON array, sorted by (surface, key), no whitespace —
 * which makes a Python json.loads byte-for-byte comparison trivial.
 */
public final class DestinationTypesProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            List<String> entries = new ArrayList<>();

            // Modern /Names /Dests name tree.
            PDDocumentNameDictionary names = catalog.getNames();
            if (names != null) {
                PDDestinationNameTreeNode dests = names.getDests();
                if (dests != null) {
                    Map<String, PDPageDestination> map = dests.getNames();
                    if (map != null) {
                        TreeMap<String, PDPageDestination> sorted = new TreeMap<>(map);
                        for (Map.Entry<String, PDPageDestination> e : sorted.entrySet()) {
                            entries.add(describe("tree", e.getKey(), e.getValue()));
                        }
                    }
                }
            }

            // Legacy catalog /Dests flat dictionary. Resolved through the catalog
            // so the same PDDestination.create() dispatch decodes the array.
            COSBase legacy = catalog.getCOSObject().getDictionaryObject(COSName.DESTS);
            if (legacy instanceof org.apache.pdfbox.cos.COSDictionary) {
                org.apache.pdfbox.cos.COSDictionary legacyDict =
                        (org.apache.pdfbox.cos.COSDictionary) legacy;
                List<COSName> keys = new ArrayList<>(legacyDict.keySet());
                keys.sort((a, b) -> a.getName().compareTo(b.getName()));
                for (COSName k : keys) {
                    PDNamedDestination nd = new PDNamedDestination(k.getName());
                    PDPageDestination dest = catalog.findNamedDestinationPage(nd);
                    entries.add(describe("dests", k.getName(), dest));
                }
            }

            // Emit one JSON array, comma-separated, no whitespace.
            StringBuilder sb = new StringBuilder();
            sb.append('[');
            for (int i = 0; i < entries.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(entries.get(i));
            }
            sb.append(']');
            out.print(sb);
        }
    }

    private static String describe(String surface, String key, PDPageDestination dest) {
        StringBuilder sb = new StringBuilder();
        sb.append('{');
        sb.append("\"surface\":\"").append(escape(surface)).append("\",");
        sb.append("\"key\":\"").append(escape(key)).append("\",");
        if (dest == null) {
            sb.append("\"dest_type\":null,");
            sb.append("\"type_name\":null,");
            sb.append("\"page_index\":-1,");
            sb.append("\"left\":null,\"top\":null,\"right\":null,")
              .append("\"bottom\":null,\"zoom\":null");
            sb.append('}');
            return sb.toString();
        }
        sb.append("\"dest_type\":\"")
          .append(escape(dest.getClass().getSimpleName())).append("\",");
        sb.append("\"type_name\":");
        String typeName = arrayTypeName(dest);
        if (typeName == null) {
            sb.append("null");
        } else {
            sb.append('"').append(escape(typeName)).append('"');
        }
        sb.append(',');
        int pageIndex;
        try {
            pageIndex = dest.retrievePageNumber();
        } catch (Exception e) {
            pageIndex = -1;
        }
        sb.append("\"page_index\":").append(pageIndex).append(',');
        sb.append("\"left\":").append(coord(left(dest))).append(',');
        sb.append("\"top\":").append(coord(top(dest))).append(',');
        sb.append("\"right\":").append(coord(right(dest))).append(',');
        sb.append("\"bottom\":").append(coord(bottom(dest))).append(',');
        sb.append("\"zoom\":").append(coord(zoom(dest)));
        sb.append('}');
        return sb.toString();
    }

    private static String arrayTypeName(PDPageDestination dest) {
        COSBase cos = dest.getCOSObject();
        if (cos instanceof COSArray) {
            String n = ((COSArray) cos).getName(1);
            if (n != null) {
                return n;
            }
        }
        return null;
    }

    /**
     * Read the left x-coordinate where the concrete class defines one.
     * Upstream's int -1 sentinel is normalised to null so the JSON survives
     * the "retain" semantics. PDPageXYZDestination, PDPageFitHeightDestination
     * (and its FitBV variant which reuses the same class) and
     * PDPageFitRectangleDestination expose a left accessor.
     */
    private static Float left(PDPageDestination dest) {
        if (dest instanceof PDPageXYZDestination) {
            return floatOrNull(((PDPageXYZDestination) dest).getLeft());
        }
        if (dest instanceof PDPageFitHeightDestination) {
            return intOrNull(((PDPageFitHeightDestination) dest).getLeft());
        }
        if (dest instanceof PDPageFitRectangleDestination) {
            return intOrNull(((PDPageFitRectangleDestination) dest).getLeft());
        }
        return null;
    }

    private static Float top(PDPageDestination dest) {
        if (dest instanceof PDPageXYZDestination) {
            return floatOrNull(((PDPageXYZDestination) dest).getTop());
        }
        if (dest instanceof PDPageFitWidthDestination) {
            return intOrNull(((PDPageFitWidthDestination) dest).getTop());
        }
        if (dest instanceof PDPageFitRectangleDestination) {
            return intOrNull(((PDPageFitRectangleDestination) dest).getTop());
        }
        return null;
    }

    private static Float right(PDPageDestination dest) {
        if (dest instanceof PDPageFitRectangleDestination) {
            return intOrNull(((PDPageFitRectangleDestination) dest).getRight());
        }
        return null;
    }

    private static Float bottom(PDPageDestination dest) {
        if (dest instanceof PDPageFitRectangleDestination) {
            return intOrNull(((PDPageFitRectangleDestination) dest).getBottom());
        }
        return null;
    }

    private static Float zoom(PDPageDestination dest) {
        if (dest instanceof PDPageXYZDestination) {
            return floatOrNull(((PDPageXYZDestination) dest).getZoom());
        }
        return null;
    }

    private static Float intOrNull(int v) {
        // Upstream sentinel for "retain current value" is -1 on int getters.
        return v == -1 ? null : (float) v;
    }

    private static Float floatOrNull(float v) {
        // Upstream sentinel for "retain current value" is -1.0f on the XYZ
        // float getters (getLeft / getTop / getZoom on PDPageXYZDestination).
        return v == -1.0f ? null : v;
    }

    private static String coord(Float v) {
        if (v == null) {
            return "null";
        }
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString(v.intValue());
        }
        return Float.toString(v);
    }

    private static String escape(String s) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }
}
