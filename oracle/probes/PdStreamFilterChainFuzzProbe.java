import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDStream;

/**
 * Live oracle probe for the READ side of
 * {@code org.apache.pdfbox.pdmodel.common.PDStream}'s filter-chain
 * accessors against malformed {@code /Filter} / {@code /DecodeParms}
 * (and the {@code /F*} external-file variants). Wave 1529, agent D.
 *
 * <p>Complements {@code PdStreamEncodeProbe} (which covers the encode /
 * addCompression write path). This probe builds a bare {@code COSStream}
 * in-process, plants a fuzzed {@code /Filter} + {@code /DecodeParms}
 * (and optionally {@code /DP}, {@code /FFilter}, {@code /FDecodeParms})
 * shape selected by a case id, wraps it in a {@code PDStream}, then
 * projects the normalised accessor outputs:
 *
 * <pre>
 *   getFilters()            -&gt; ordered name list (or ERR class)
 *   getDecodeParms()        -&gt; element count + per-element kind
 *   getFileFilters()        -&gt; ordered name-string list (or ERR class)
 *   getFileDecodeParams()   -&gt; element count + per-element kind
 *   getDecodedStreamLength() -&gt; the /DL int
 * </pre>
 *
 * <h2>Case ids</h2> (args[0..]) — one line of output per id, in order:
 * <pre>
 *   CASE &lt;id&gt; filters=&lt;...&gt; parms=&lt;...&gt; ffilters=&lt;...&gt; fparms=&lt;...&gt; dl=&lt;int&gt;
 * </pre>
 * The {@code filters} projection is {@code name,name,...} (empty -&gt;
 * {@code -}); a non-name array element is rendered by its COS class
 * simple name. {@code parms} is {@code null} when the accessor returns
 * null, else the element count followed by {@code :kind,kind} where kind
 * is {@code dict} (a real {@code COSDictionary}/map) or the simple class
 * name of whatever else survived. {@code ERR:<Exc>} if the accessor threw.
 */
public final class PdStreamFilterChainFuzzProbe {

    static final COSName FILTER = COSName.FILTER;
    static final COSName DECODE_PARMS = COSName.DECODE_PARMS;
    static final COSName DP = COSName.DP;
    static final COSName F_FILTER = COSName.F_FILTER;
    static final COSName F_DECODE_PARMS = COSName.F_DECODE_PARMS;
    static final COSName DL = COSName.DL;

    static COSStream build(String id) {
        COSStream s = new COSStream();
        switch (id) {
            case "filter_absent":
                break;
            case "filter_single_name":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                break;
            case "filter_array_one":
                s.setItem(FILTER, arr(COSName.FLATE_DECODE));
                break;
            case "filter_array_two":
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                break;
            case "filter_array_empty":
                s.setItem(FILTER, new COSArray());
                break;
            case "filter_unknown_name":
                s.setItem(FILTER, COSName.getPDFName("BogusDecode"));
                break;
            case "filter_string_invalid":
                s.setItem(FILTER, new COSString("FlateDecode"));
                break;
            case "filter_int_invalid":
                s.setItem(FILTER, COSInteger.get(7));
                break;
            case "filter_array_with_string":
                s.setItem(FILTER, arr(COSName.FLATE_DECODE, new COSString("x")));
                break;
            case "filter_array_with_null":
                COSArray fa = new COSArray();
                fa.add(COSName.FLATE_DECODE);
                fa.add(COSNull.NULL);
                s.setItem(FILTER, fa);
                break;
            case "parms_absent":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                break;
            case "parms_single_dict":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, dict("Predictor", 12));
                break;
            case "parms_array_two":
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                COSArray pa = new COSArray();
                pa.add(dict("a", 1));
                pa.add(dict("Predictor", 12));
                s.setItem(DECODE_PARMS, pa);
                break;
            case "parms_array_with_null":
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                COSArray pn = new COSArray();
                pn.add(COSNull.NULL);
                pn.add(dict("Predictor", 12));
                s.setItem(DECODE_PARMS, pn);
                break;
            case "parms_array_all_null":
                s.setItem(FILTER, arr(COSName.FLATE_DECODE, COSName.FLATE_DECODE));
                COSArray pan = new COSArray();
                pan.add(COSNull.NULL);
                pan.add(COSNull.NULL);
                s.setItem(DECODE_PARMS, pan);
                break;
            case "parms_array_with_nondict":
                s.setItem(FILTER, arr(COSName.FLATE_DECODE, COSName.FLATE_DECODE));
                COSArray pnd = new COSArray();
                pnd.add(dict("Predictor", 12));
                pnd.add(COSName.getPDFName("Oops"));
                s.setItem(DECODE_PARMS, pnd);
                break;
            case "parms_name_invalid":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, COSName.getPDFName("Nope"));
                break;
            case "parms_int_invalid":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, COSInteger.get(3));
                break;
            case "parms_dp_alias_only":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DP, dict("Predictor", 15));
                break;
            case "parms_dp_and_canonical":
                // canonical present -> /DP must be ignored.
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DECODE_PARMS, dict("Predictor", 2));
                s.setItem(DP, dict("Predictor", 99));
                break;
            case "parms_single_dict_filter_array":
                // single /DecodeParms dict but /Filter is a 2-name array.
                s.setItem(FILTER, arr(COSName.ASCII85_DECODE, COSName.FLATE_DECODE));
                s.setItem(DECODE_PARMS, dict("Predictor", 12));
                break;
            case "parms_array_filter_single":
                // /DecodeParms array but /Filter is a single name.
                s.setItem(FILTER, COSName.FLATE_DECODE);
                COSArray pas = new COSArray();
                pas.add(dict("Predictor", 12));
                s.setItem(DECODE_PARMS, pas);
                break;
            case "parms_len_mismatch_more":
                // 1 filter, 2 parms.
                s.setItem(FILTER, arr(COSName.FLATE_DECODE));
                COSArray pm = new COSArray();
                pm.add(dict("Predictor", 12));
                pm.add(dict("Predictor", 2));
                s.setItem(DECODE_PARMS, pm);
                break;
            case "ffilter_array_with_null":
                COSArray ff = new COSArray();
                ff.add(COSName.FLATE_DECODE);
                ff.add(COSNull.NULL);
                s.setItem(F_FILTER, ff);
                COSArray ffp = new COSArray();
                ffp.add(COSNull.NULL);
                ffp.add(dict("Predictor", 12));
                s.setItem(F_DECODE_PARMS, ffp);
                break;
            case "ffilter_single_fparms_array":
                s.setItem(F_FILTER, COSName.FLATE_DECODE);
                COSArray ffp2 = new COSArray();
                ffp2.add(dict("Predictor", 12));
                s.setItem(F_DECODE_PARMS, ffp2);
                break;
            case "fparms_name_invalid":
                s.setItem(F_FILTER, COSName.FLATE_DECODE);
                s.setItem(F_DECODE_PARMS, COSName.getPDFName("Nope"));
                break;
            case "dl_set":
                s.setItem(FILTER, COSName.FLATE_DECODE);
                s.setItem(DL, COSInteger.get(4242));
                break;
            default:
                throw new IllegalArgumentException("unknown case " + id);
        }
        return s;
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    static COSDictionary dict(String key, int value) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.getPDFName(key), COSInteger.get(value));
        return d;
    }

    static String filtersProj(PDStream pd) {
        try {
            List<COSName> fs = pd.getFilters();
            if (fs.isEmpty()) {
                return "-";
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < fs.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                Object o = fs.get(i);
                if (o instanceof COSName) {
                    sb.append(((COSName) o).getName());
                } else {
                    sb.append(o.getClass().getSimpleName());
                }
            }
            return sb.toString();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String ffiltersProj(PDStream pd) {
        try {
            List<String> fs = pd.getFileFilters();
            if (fs.isEmpty()) {
                return "-";
            }
            return String.join(",", fs);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String parmsProj(List<?> parms) {
        if (parms == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder();
        sb.append(parms.size());
        sb.append(':');
        for (int i = 0; i < parms.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            Object o = parms.get(i);
            if (o == null) {
                sb.append("none");
            } else if (o instanceof java.util.Map) {
                sb.append("dict");
            } else {
                sb.append(o.getClass().getSimpleName());
            }
        }
        return sb.toString();
    }

    static String decodeParmsProj(PDStream pd) {
        try {
            return parmsProj(pd.getDecodeParms());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String fileParmsProj(PDStream pd) {
        try {
            return parmsProj(pd.getFileDecodeParams());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    public static void main(String[] args) {
        StringBuilder out = new StringBuilder();
        for (String id : args) {
            String filters;
            String parms;
            String ffilters;
            String fparms;
            String dl;
            try {
                PDStream pd = new PDStream(build(id));
                filters = filtersProj(pd);
                parms = decodeParmsProj(pd);
                ffilters = ffiltersProj(pd);
                fparms = fileParmsProj(pd);
                dl = Integer.toString(pd.getDecodedStreamLength());
            } catch (Exception e) {
                filters = "BUILD:" + e.getClass().getSimpleName();
                parms = "-";
                ffilters = "-";
                fparms = "-";
                dl = "-";
            }
            out.append("CASE ").append(id)
                    .append(" filters=").append(filters)
                    .append(" parms=").append(parms)
                    .append(" ffilters=").append(ffilters)
                    .append(" fparms=").append(fparms)
                    .append(" dl=").append(dl)
                    .append('\n');
        }
        System.out.print(out);
    }
}
