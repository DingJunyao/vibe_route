/**
 * 道路编号解析工具
 * 用于将数据库中存储的道路编号解析为道路标志生成所需的参数
 */

export interface ParsedRoadNumber {
  original: string      // 原始编号，如 "豫S88"
  sign_type: 'way' | 'expwy'
  code: string          // 规范化编号，如 "S88"
  province?: string     // 省份简称，如 "豫"
}

// 省份简称列表
const PROVINCES = ['京', '津', '冀', '晋', '蒙', '辽', '吉', '黑', '沪', '苏', '浙', '皖', '闽', '赣', '鲁', '豫', '鄂', '湘', '粤', '桂', '琼', '渝', '川', '贵', '云', '藏', '陕', '甘', '青', '宁', '新']

/**
 * 解析道路编号，判断其类型
 *
 * 判断顺序很重要：
 * 1. 先匹配普通道路（G/S/X + 三位数字）——最严格的格式
 * 2. 再匹配国家高速（G + 1-4位数字）
 * 3. 再匹配四川省级高速（S + 字母 + 可选数字）
 * 4. 最后匹配省级高速（S + 1-4位纯数字）
 *
 * @param code 数据库中的道路编号，如 "G221", "豫S88", "川SA"
 * @returns 解析后的道路编号信息，如果无法解析则返回 null
 */
export function parseRoadNumber(code: string): ParsedRoadNumber | null {
  const trimmed = code.trim().toUpperCase()
  if (!trimmed) return null

  // 检查是否有省份前缀（中文省份 + 字母 + 数字）
  // 匹配：第一个字符是中文（或字母），第二个字符是字母，后面是任意字符
  const provinceMatch = trimmed.match(/^([^\x00-\x7F])([A-Z])(.+)$/)
  if (provinceMatch) {
    const [_, province, letter, number] = provinceMatch
    const fullCode = letter + number  // 如 "S88"

    // 检查是否是有效省份
    if (!PROVINCES.includes(province)) {
      // 不是有效省份，按无省份处理
      return parseRoadNumberWithoutProvince(trimmed)
    }

    // ===== 带省份的解析 =====

    // 1. 国道/省道：省份 + G/S + 三位数字（如 豫S221, 冀G221）
    if (/^[GS]\d{3}$/.test(fullCode)) {
      return { original: code, sign_type: 'way', code: fullCode }
    }

    // 2. 县道：省份 + X + 三位数字，或省份 + 除 G/S 外的其他字母 + 三位数字（如 豫X001, 豫Y008）
    if (/^[A-Z]\d{3}$/.test(fullCode)) {
      return { original: code, sign_type: 'way', code: fullCode }
    }

    // 2. 四川省级高速（字母格式）：省份 + S + 字母 + 可选数字（如 川SA, 川SA1, 川SC）
    if (province === '川' && letter === 'S') {
      const letterFormatMatch = fullCode.match(/^S([A-Z]\d{0,3})$/)
      if (letterFormatMatch) {
        return { original: code, sign_type: 'expwy', code: fullCode, province }
      }
    }

    // 3. 省级高速：省份 + S + 1-4位纯数字（如 豫S88）
    if (letter === 'S' && /^\d{1,4}$/.test(number)) {
      return { original: code, sign_type: 'expwy', code: fullCode, province }
    }

    // 其他格式按无省份处理
    return parseRoadNumberWithoutProvince(trimmed)
  }

  // 无省份前缀，直接解析
  return parseRoadNumberWithoutProvince(trimmed)
}

/**
 * 解析不带省份前缀的道路编号
 */
function parseRoadNumberWithoutProvince(code: string): ParsedRoadNumber | null {
  const trimmed = code.trim().toUpperCase()
  if (!trimmed) return null

  // ===== 无省份的解析（判断顺序很重要）=====

  // 1. 国道/省道：G/S + 三位数字（如 G221, S221）
  if (/^[GS]\d{3}$/.test(trimmed)) {
    return { original: code, sign_type: 'way', code: trimmed }
  }

  // 2. 县道：X + 三位数字，或除 G/S 外的其他字母 + 三位数字（如 X001, Y008）
  if (/^[A-Z]\d{3}$/.test(trimmed)) {
    return { original: code, sign_type: 'way', code: trimmed }
  }

  // 3. 国家高速：G + 1-4位数字（如 G5, G45, G4511）
  if (/^G\d{1,4}$/.test(trimmed)) {
    return { original: code, sign_type: 'expwy', code: trimmed }
  }

  // 4. 四川省级高速（字母格式）：S + 字母 + 可选数字（如 SA, SC, SA1）
  // 注意：无省份时，这种格式只对四川有效，但我们无法确定省份
  // 这里保守处理：只当作普通道路或不解析
  // 如果数据库中有省份前缀，会在上面的分支处理

  // 5. 省级高速：S + 1-4位纯数字（如 S1, S11, S111）
  // 注意：无省份时无法区分是省道还是省级高速
  // 保守处理：当作普通道路
  if (/^S\d{1,4}$/.test(trimmed)) {
    return { original: code, sign_type: 'way', code: trimmed }
  }

  return null
}
