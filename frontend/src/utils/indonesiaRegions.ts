export interface IndonesiaRegion {
  code: string
  name: string
}

export const indonesiaRegions: IndonesiaRegion[] = [
  { code: '1', name: '亚齐' },
  { code: '2', name: '北苏门答腊' },
  { code: '3', name: '廖内' },
  { code: '4', name: '西苏门答腊' },
  { code: '5', name: '占碑' },
  { code: '6', name: '南苏门答腊' },
  { code: '7', name: '明古鲁' },
  { code: '8', name: '楠榜' },
  { code: '9', name: '廖内群岛' },
  { code: '10', name: '邦加勿里洞群岛' },
  { code: '11', name: '万丹' },
  { code: '12', name: '西爪哇' },
  { code: '13', name: '雅加达' },
  { code: '14', name: '中爪哇' },
  { code: '15', name: '日惹' },
  { code: '16', name: '东爪哇' },
  { code: '17', name: '巴厘' },
  { code: '18', name: '西努沙登加拉' },
  { code: '19', name: '东努沙登加拉' },
  { code: '20', name: '西加里曼丹' },
  { code: '21', name: '中加里曼丹' },
  { code: '22', name: '南加里曼丹' },
  { code: '23', name: '东加里曼丹' },
  { code: '24', name: '北加里曼丹' },
  { code: '25', name: '南苏拉威西' },
  { code: '26', name: '西苏拉威西' },
  { code: '27', name: '东南苏拉威西' },
  { code: '28', name: '中苏拉威西' },
  { code: '29', name: '哥伦打洛' },
  { code: '30', name: '北苏拉威西' },
  { code: '31', name: '马鲁古' },
  { code: '32', name: '北马鲁古' },
  { code: '33', name: '西巴布亚' },
  { code: '34', name: '巴布亚' },
]

export type IndonesiaRoadType = 'tol' | 'national' | 'other'

export function normalizeIndonesiaRoadCode(value: string): string {
  return value.replace(/\D/g, '')
}

export function validateIndonesiaRoadInput(
  roadType: IndonesiaRoadType,
  regionCode: string,
  code: string,
): string | null {
  if (!regionCode) {
    return '请选择地区'
  }

  const normalizedCode = normalizeIndonesiaRoadCode(code).trim()
  if (!normalizedCode) {
    return '请输入道路编号'
  }

  const expectedLength = roadType === 'other' ? 3 : 2
  if (
    (roadType === 'other' && normalizedCode.length !== expectedLength) ||
    (roadType !== 'other' && normalizedCode.length > expectedLength)
  ) {
    return roadType === 'other'
      ? '其他道路编号应为 3 位数字'
      : '道路编号应为 1-2 位数字'
  }

  return null
}
