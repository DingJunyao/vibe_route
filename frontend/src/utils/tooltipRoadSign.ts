/**
 * 地图 tooltip 气泡的道路编号盾牌渲染（五个地图引擎组件共用）
 *
 * 按点级 region 分派，与区域树 renderNodeLabel 口径一致：
 * - cn: 前端 parseRoadNumber 解析国标编号，后端生成国标盾牌
 * - id: 编号不经前端解析，原样交后端按编号 + 路名判级生成六边形盾牌
 * 生成失败或编号无法解析时回退纯文本。
 *
 * 缓存与防重集合为模块级，五个地图组件共享（同一盾牌只请求一次后端）。
 */
import { escapeHtml } from '@/utils/format'
import { roadSignApi } from '@/api/roadSign'
import { useConfigStore } from '@/stores/config'
import { parseRoadNumber } from '@/utils/roadSignParser'

/** 一个待加载/渲染的盾牌参数（id 时 signType 恒 'way'，等级由后端判定） */
export interface TooltipSignLoad {
  region: string
  code: string
  signType: 'way' | 'expwy'
  province?: string
  name?: string
  nameId?: string
}

/** tooltip 渲染所需的点级地理字段（地图组件 Point 的子集） */
export interface TooltipSignPoint {
  region?: string | null
  road_number?: string | null
  road_name?: string | null
  road_name_id?: string | null
  road_name_en?: string | null
}

const roadSignSvgCache = new Map<string, string>()
const loadingSigns = new Set<string>()

/**
 * 缓存键：cn 维持历史键（signType:code[:province]，与旧组件级缓存兼容）；
 * id 含中/印尼语路名（后端对两段文本联合判 TOL，「同编号不同路名」不能串用），
 * 用 JSON 数组而非 join(':')：成分含冒号或为空时不会跨字段错位，天然单射。
 */
export function buildTooltipSignKey(opts: TooltipSignLoad): string {
  if (opts.region !== 'cn') {
    return JSON.stringify([opts.region, opts.signType, opts.code, opts.name ?? '', opts.nameId ?? ''])
  }
  return opts.province ? `${opts.signType}:${opts.code}:${opts.province}` : `${opts.signType}:${opts.code}`
}

/** 清理 SVG 字符串：只压缩空白，不修改结构（显示样式由外层 span 控制） */
function sanitizeSvg(svg: string): string {
  return svg.replace(/\s+/g, ' ').trim()
}

/** 异步获取盾牌 SVG（缓存命中直接返回；失败返回 null 走文本回退） */
async function getRoadSignSvg(opts: TooltipSignLoad): Promise<string | null> {
  const cacheKey = buildTooltipSignKey(opts)
  const cached = roadSignSvgCache.get(cacheKey)
  if (cached) return cached

  try {
    const isId = opts.region !== 'cn'
    const response = await roadSignApi.generate({
      sign_type: isId ? 'way' : opts.signType,  // id: sign_type 无意义，后端忽略
      code: opts.code,
      ...(opts.province && { province: opts.province }),
      ...(opts.name && { name: opts.name }),
      ...(isId && { region: opts.region }),
      ...(isId && opts.nameId && { name_id: opts.nameId }),
    })
    if (typeof response.svg !== 'string') return null
    const cleanSvg = sanitizeSvg(response.svg)
    roadSignSvgCache.set(cacheKey, cleanSvg)
    return cleanSvg
  } catch {
    return null
  }
}

/**
 * 渲染 tooltip 的道路编号段：缓存命中出盾牌 SVG，未命中出文本并记入 needLoad。
 * @returns html 为编号段 HTML（无编号时 null），needLoad 供 loadTooltipRoadSigns 异步补载
 */
export function formatTooltipRoadSigns(point: TooltipSignPoint): { html: string | null; needLoad: TooltipSignLoad[] } {
  if (!point.road_number) return { html: null, needLoad: [] }

  const region = point.region || 'cn'
  const roadNumbers = String(point.road_number).split(',').map(s => s.trim())
  const contents: string[] = []
  const needLoad: TooltipSignLoad[] = []

  for (const num of roadNumbers) {
    let opts: TooltipSignLoad | null = null
    if (region !== 'cn') {
      // 印尼：编号原样交后端；中文路名缺省时兜底印尼语/英语（TOL 判定文本）
      const name = point.road_name || point.road_name_id || point.road_name_en || ''
      opts = {
        region,
        code: num,
        signType: 'way',
        ...(name && { name }),
        ...(point.road_name_id && { nameId: point.road_name_id }),
      }
    } else {
      const parsed = parseRoadNumber(num)
      if (parsed) {
        opts = {
          region: 'cn',
          code: parsed.code,
          signType: parsed.sign_type,
          ...(parsed.province && { province: parsed.province }),
        }
      }
    }

    if (opts) {
      const svg = roadSignSvgCache.get(buildTooltipSignKey(opts))
      if (svg) {
        // 内联样式兜底 Leaflet/ECharts 等不经过组件 :deep 样式作用的容器
        contents.push(`<span class="road-sign-inline" style="display: inline-flex; align-items: center; vertical-align: middle; line-height: 1; margin: 0 1px;">${svg}</span>`)
      } else {
        contents.push(escapeHtml(num))
        needLoad.push(opts)
      }
    } else {
      // 编号无法解析（如 cn 分支的印尼格式编号），纯文本
      contents.push(escapeHtml(num))
    }
  }

  return { html: contents.length > 0 ? contents.join(' ') : null, needLoad }
}

/**
 * 异步加载 tooltip 盾牌（受配置 show_road_sign_in_region_tree 控制，关闭时不请求）。
 * @returns 任一盾牌就绪即为 true，调用方据此刷新 tooltip 内容
 */
export async function loadTooltipRoadSigns(needLoad: TooltipSignLoad[]): Promise<boolean> {
  const config = useConfigStore().config
  const showSigns = config?.show_road_sign_in_region_tree ?? true
  if (!showSigns || needLoad.length === 0) return false

  let loaded = false
  for (const opts of needLoad) {
    const key = buildTooltipSignKey(opts)
    if (loadingSigns.has(key)) continue

    loadingSigns.add(key)
    try {
      const svg = await getRoadSignSvg(opts)
      if (svg) {
        loaded = true
      }
    } finally {
      loadingSigns.delete(key)
    }
  }

  return loaded
}
