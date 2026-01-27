<template>
  <div ref="containerRef" class="track-detail-container">
    <el-header>
      <div class="header-left">
        <el-button @click="$router.back()" :icon="ArrowLeft">返回</el-button>
        <div class="title-with-tags">
          <h1>{{ track?.name || '轨迹详情' }}</h1>
          <el-tag v-if="track?.is_live_recording && track.live_recording_status === 'active'" type="success" size="small" class="title-tag">
            实时轨迹记录中
          </el-tag>
        </div>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <el-button
            v-if="track?.is_live_recording && track.live_recording_token"
            type="warning"
            @click="showRecordingDetail"
            class="desktop-only"
          >
            <el-icon><Link /></el-icon>
            记录配置
          </el-button>
          <el-button type="primary" @click="showEditDialog" class="desktop-only">
            <el-icon><Edit /></el-icon>
            编辑
          </el-button>
          <el-button type="primary" @click="exportPointsDialogVisible = true" class="desktop-only">
            <el-icon><Download /></el-icon>
            导出数据
          </el-button>
          <el-button type="primary" @click="importDialogVisible = true" class="desktop-only">
            <el-icon><Upload /></el-icon>
            导入数据
          </el-button>
          <el-button type="primary" @click="downloadDialogVisible = true" class="desktop-only">
            <el-icon><Document /></el-icon>
            下载 GPX
          </el-button>
          <el-button
            type="primary"
            @click="handleFillGeocoding"
            class="desktop-only"
            :loading="fillingGeocoding"
            :disabled="fillProgress.status === 'filling'"
          >
            <el-icon><LocationFilled /></el-icon>
            填充地理信息
          </el-button>
        </div>
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            <span class="username">{{ authStore.user?.username }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                command="recordingDetail"
                v-if="isMobile && track?.is_live_recording && track.live_recording_token"
              >
                <el-icon><Link /></el-icon>
                记录配置
              </el-dropdown-item>
              <el-dropdown-item command="edit" v-if="isMobile">
                <el-icon><Edit /></el-icon>
                编辑
              </el-dropdown-item>
              <el-dropdown-item command="exportPoints" v-if="isMobile">
                <el-icon><Download /></el-icon>
                导出数据
              </el-dropdown-item>
              <el-dropdown-item command="import" v-if="isMobile">
                <el-icon><Upload /></el-icon>
                导入数据
              </el-dropdown-item>
              <el-dropdown-item command="download" v-if="isMobile">
                <el-icon><Document /></el-icon>
                下载 GPX
              </el-dropdown-item>
              <el-dropdown-item
                command="fill"
                v-if="isMobile"
                :disabled="fillProgress.status === 'filling'"
              >
                <el-icon><LocationFilled /></el-icon>
                {{ fillProgress.status === 'filling' ? '填充中...' : '填充地理信息' }}
              </el-dropdown-item>
              <el-dropdown-item command="admin" v-if="authStore.user?.is_admin">
                <el-icon><Setting /></el-icon>
                后台管理
              </el-dropdown-item>
              <el-dropdown-item command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-main class="main" :class="{ 'main-fixed': isTallScreen }" v-loading="loading">
      <!-- 调试信息 -->
      <el-alert v-if="!track" type="error" :closable="false" style="margin-bottom: 20px">
        轨迹数据加载失败，请返回列表重试
      </el-alert>

      <template v-if="track">
        <!-- 固定布局容器（高屏时使用） -->
        <div v-if="isTallScreen" class="fixed-layout">
          <!-- 左侧固定区域 -->
          <div class="fixed-left">
            <!-- 地图 -->
            <el-card class="map-card" shadow="never">
              <template v-if="trackWithPoints">
                <div ref="mapWrapperRef" class="map-wrapper">
                  <UniversalMap
                    ref="mapRef"
                    :tracks="[trackWithPoints]"
                    :highlight-track-id="track.id"
                    :highlight-segment="highlightedSegment"
                    @point-hover="handleMapPointHover"
                    @clear-segment-highlight="clearSegmentHighlight"
                  />
                </div>
              </template>
              <template v-else>
                <div class="map-placeholder">
                  <p>{{ points.length === 0 ? '正在加载轨迹点数据...' : '轨迹点坐标数据无效' }}</p>
                  <p v-if="points.length > 0" class="debug-info">
                    轨迹点数量: {{ points.length }}，
                    有效坐标: {{ points.filter(p => p.latitude_wgs84 != null && p.longitude_wgs84 != null).length }}
                  </p>
                  <el-button size="small" @click="$router.push('/upload')">上传新轨迹</el-button>
                </div>
              </template>
            </el-card>

            <!-- 海拔和速度图表 -->
            <el-card class="chart-card" shadow="never">
              <template #header>
                <span>海拔与速度变化</span>
              </template>
              <div ref="chartRef" class="chart"></div>
            </el-card>
          </div>

          <!-- 右侧滚动区域 -->
          <div class="scrollable-right">
            <el-row :gutter="20">
              <el-col :xs="24" :md="24">
                <!-- 统计信息 -->
                <el-card class="stats-card" shadow="never">
                  <template #header>
                    <span>轨迹信息</span>
                  </template>
                  <!-- 起止时间 -->
                  <div class="time-range-section" :class="{ 'same-day': isSameDay(track.start_time, track.end_time) }">
                    <div class="time-range-item">
                      <div class="time-range-content">
                        <div class="time-range-time">{{ formatTimeOnly(track.start_time) }}</div>
                        <div class="time-range-date">{{ formatDate(track.start_time) }}</div>
                      </div>
                    </div>
                    <div class="time-range-divider">
                      <template v-if="isSameDay(track.start_time, track.end_time)">
                        <span class="time-range-divider-date">{{ formatDate(track.start_time) }}</span>
                      </template>
                      <el-icon v-else class="time-range-divider-icon"><Clock /></el-icon>
                    </div>
                    <div class="time-range-item">
                      <div class="time-range-content">
                        <div class="time-range-time">{{ formatTimeOnly(track.end_time) }}</div>
                        <div class="time-range-date">{{ formatDate(track.end_time) }}</div>
                      </div>
                    </div>
                  </div>
                  <el-divider style="margin: 16px 0;"></el-divider>
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <div class="stat-item">
                        <el-icon class="stat-icon" color="#409eff"><Odometer /></el-icon>
                        <div class="stat-content">
                          <div class="stat-value">{{ formatDistance(track.distance) }}</div>
                          <div class="stat-label">总里程</div>
                        </div>
                      </div>
                    </el-col>
                    <el-col :span="12">
                      <div class="stat-item">
                        <el-icon class="stat-icon" color="#67c23a"><Clock /></el-icon>
                        <div class="stat-content">
                          <div class="stat-value">{{ formatDuration(track.duration) }}</div>
                          <div class="stat-label">总时长</div>
                        </div>
                      </div>
                    </el-col>
                    <el-col :span="12">
                      <div class="stat-item">
                        <el-icon class="stat-icon" color="#e6a23c"><Top /></el-icon>
                        <div class="stat-content">
                          <div class="stat-value">{{ formatElevation(track.elevation_gain) }}</div>
                          <div class="stat-label">总爬升</div>
                        </div>
                      </div>
                    </el-col>
                    <el-col :span="12">
                      <div class="stat-item">
                        <el-icon class="stat-icon" color="#f56c6c"><Bottom /></el-icon>
                        <div class="stat-content">
                          <div class="stat-value">{{ formatElevation(track.elevation_loss) }}</div>
                          <div class="stat-label">总下降</div>
                        </div>
                      </div>
                    </el-col>
                  </el-row>
                  <!-- 备注 -->
                  <div v-if="track.description" class="description-section">
                    <el-divider style="margin: 16px 0;"></el-divider>
                    <div class="description-text">{{ track.description }}</div>
                  </div>
                </el-card>

                <!-- 经过的区域 - 树形展示 -->
                <el-card class="areas-card" shadow="never">
                  <template #header>
                    <div class="card-header">
                      <span>经过区域</span>
                      <el-tag v-if="regionStats.province > 0" size="small" type="info">
                        {{ regionStats.province }} 省级 / {{ regionStats.city }} 地级 / {{ regionStats.district }} 县级
                      </el-tag>
                    </div>
                  </template>

                  <!-- 未填充提示（仅在未填充且未开始填充时显示） -->
                  <div v-if="(!track.has_area_info || !track.has_road_info) && !(fillProgress.status === 'filling' || fillingGeocoding)" class="no-fill-hint">
                    <el-icon><LocationFilled /></el-icon>
                    <span>请填充地理信息后查看</span>
                    <div class="no-fill-actions">
                      <el-button type="primary" size="small" @click="handleFillGeocoding" :loading="fillingGeocoding">
                        立即填充
                      </el-button>
                      <el-button type="success" size="small" @click="importDialogVisible = true">
                        导入数据
                      </el-button>
                    </div>
                  </div>

                  <!-- 填充进度（开始填充后显示，无论是否已填充） -->
                  <template v-if="fillProgress.status === 'filling' || fillingGeocoding">
                    <div class="fill-progress-section">
                      <div class="fill-progress-hint">正在填充地理信息……</div>
                      <div class="fill-progress-with-action">
                        <el-progress
                          :percentage="fillProgressPercentage"
                          :show-text="false"
                          :stroke-width="8"
                        />
                        <el-button class="stop-fill-btn" type="danger" circle @click="handleStopFillGeocoding" />
                      </div>
                      <div class="fill-progress-text">
                        <span v-if="fillProgress.total > 0">{{ fillProgress.current }} / {{ fillProgress.total }} 点（{{ fillProgressPercentage }}%）</span>
                        <span v-else>正在准备...</span>
                      </div>
                    </div>
                  </template>

                  <!-- 区域树 -->
                  <template v-else>
                    <div v-if="regionTreeLoading" v-loading="true" style="min-height: 60px"></div>
                    <div v-else-if="regionTree.length > 0" class="region-tree-container">
                      <el-tree
                        :data="regionTree"
                        :props="{ label: 'name', children: 'children' }"
                        default-expand-all
                        :expand-on-click-node="false"
                        node-key="id"
                        :key="treeForceUpdateKey"
                        @node-click="handleRegionNodeClick"
                      >
                        <template #default="{ data }">
                          <div class="region-tree-node">
                            <div class="node-label">
                              <el-icon class="node-icon" :class="`icon-${data.type}`">
                                <LocationFilled v-if="data.type === 'province'" />
                                <LocationFilled v-else-if="data.type === 'city'" />
                                <LocationFilled v-else-if="data.type === 'district'" />
                                <Odometer v-else-if="data.type === 'road'" />
                              </el-icon>
                              <el-tag v-if="data.name === '未知区域'" type="danger" size="small">未知区域</el-tag>
                              <component v-else :is="() => renderNodeLabel(data)" />
                            </div>
                            <div class="node-info">
                              <span class="node-distance">{{ formatDistance(data.distance) }}</span>
                              <span v-if="data.start_time" class="node-time">{{ formatTimeRange(data.start_time, data.end_time) }}</span>
                            </div>
                          </div>
                        </template>
                      </el-tree>
                    </div>
                  </template>
                </el-card>
              </el-col>
            </el-row>
          </div>
        </div>

        <!-- 常规布局（低屏时使用） -->
        <div v-else class="normal-layout">
          <!-- 左侧：地图和图表 -->
          <div class="normal-left">
            <!-- 地图 -->
            <el-card class="map-card" shadow="never">
              <template v-if="trackWithPoints">
                <!-- <div style="background: #e5e5e5; padding: 10px; font-size: 12px; color: #666;">
                  调试: trackWithPoints 存在，轨迹点数: {{ trackWithPoints.points.length }}
                </div> -->
                <div class="normal-map-container">
                  <UniversalMap
                    ref="mapRef"
                    :tracks="[trackWithPoints]"
                    :highlight-track-id="track.id"
                    :highlight-segment="highlightedSegment"
                    @point-hover="handleMapPointHover"
                    @clear-segment-highlight="clearSegmentHighlight"
                  />
                </div>
              </template>
              <template v-else>
                <div class="map-placeholder">
                  <p>{{ points.length === 0 ? '正在加载轨迹点数据...' : '轨迹点坐标数据无效' }}</p>
                  <p v-if="points.length > 0" class="debug-info">
                    轨迹点数量: {{ points.length }}，
                    有效坐标: {{ points.filter(p => p.latitude_wgs84 != null && p.longitude_wgs84 != null).length }}
                  </p>
                  <el-button size="small" @click="$router.push('/upload')">上传新轨迹</el-button>
                </div>
              </template>
            </el-card>

            <!-- 海拔和速度图表 -->
            <el-card class="chart-card" shadow="never">
              <template #header>
                <span>海拔与速度变化</span>
              </template>
              <div ref="chartRef" class="chart"></div>
            </el-card>
          </div>

          <!-- 右侧：轨迹信息和区域 -->
          <div class="normal-right">
            <!-- 统计信息 -->
            <el-card class="stats-card" shadow="never">
              <template #header>
                <span>轨迹信息</span>
              </template>
              <!-- 起止时间 -->
              <div class="time-range-section" :class="{ 'same-day': isSameDay(track.start_time, track.end_time) }">
                <div class="time-range-item">
                  <div class="time-range-content">
                    <div class="time-range-time">{{ formatTimeOnly(track.start_time) }}</div>
                    <div class="time-range-date">{{ formatDate(track.start_time) }}</div>
                  </div>
                </div>
                <div class="time-range-divider">
                  <template v-if="isSameDay(track.start_time, track.end_time)">
                    <span class="time-range-divider-date">{{ formatDate(track.start_time) }}</span>
                  </template>
                  <el-icon v-else class="time-range-divider-icon"><Clock /></el-icon>
                </div>
                <div class="time-range-item">
                  <div class="time-range-content">
                    <div class="time-range-time">{{ formatTimeOnly(track.end_time) }}</div>
                    <div class="time-range-date">{{ formatDate(track.end_time) }}</div>
                  </div>
                </div>
              </div>
              <el-divider style="margin: 16px 0;"></el-divider>
              <el-row :gutter="20">
                <el-col :span="12">
                  <div class="stat-item">
                    <el-icon class="stat-icon" color="#409eff"><Odometer /></el-icon>
                    <div class="stat-content">
                      <div class="stat-value">{{ formatDistance(track.distance) }}</div>
                      <div class="stat-label">总里程</div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="stat-item">
                    <el-icon class="stat-icon" color="#67c23a"><Clock /></el-icon>
                    <div class="stat-content">
                      <div class="stat-value">{{ formatDuration(track.duration) }}</div>
                      <div class="stat-label">总时长</div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="stat-item">
                    <el-icon class="stat-icon" color="#e6a23c"><Top /></el-icon>
                    <div class="stat-content">
                      <div class="stat-value">{{ formatElevation(track.elevation_gain) }}</div>
                      <div class="stat-label">总爬升</div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="stat-item">
                    <el-icon class="stat-icon" color="#f56c6c"><Bottom /></el-icon>
                    <div class="stat-content">
                      <div class="stat-value">{{ formatElevation(track.elevation_loss) }}</div>
                      <div class="stat-label">总下降</div>
                    </div>
                  </div>
                </el-col>
              </el-row>
              <!-- 备注 -->
              <div v-if="track.description" class="description-section">
                <el-divider style="margin: 16px 0;"></el-divider>
                <div class="description-text">{{ track.description }}</div>
              </div>
            </el-card>

            <!-- 经过的区域 - 树形展示 -->
            <el-card class="areas-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>经过区域</span>
                  <el-tag v-if="regionStats.province > 0" size="small" type="info">
                    {{ regionStats.province }} 省级 / {{ regionStats.city }} 地级 / {{ regionStats.district }} 县级
                  </el-tag>
                </div>
              </template>

              <!-- 未填充提示（仅在未填充且未开始填充时显示） -->
              <div v-if="(!track.has_area_info || !track.has_road_info) && !(fillProgress.status === 'filling' || fillingGeocoding)" class="no-fill-hint">
                <el-icon><LocationFilled /></el-icon>
                <span>请填充地理信息后查看</span>
                <div class="no-fill-actions">
                  <el-button type="primary" size="small" @click="handleFillGeocoding" :loading="fillingGeocoding">
                    立即填充
                  </el-button>
                  <el-button type="success" size="small" @click="importDialogVisible = true">
                    导入数据
                  </el-button>
                </div>
              </div>

              <!-- 填充进度（开始填充后显示，无论是否已填充） -->
              <template v-if="fillProgress.status === 'filling' || fillingGeocoding">
                <div class="fill-progress-section">
                  <div class="fill-progress-hint">正在填充地理信息……</div>
                  <div class="fill-progress-with-action">
                    <el-progress
                      :percentage="fillProgressPercentage"
                      :show-text="false"
                      :stroke-width="8"
                    />
                    <el-button class="stop-fill-btn" type="danger" circle @click="handleStopFillGeocoding" />
                  </div>
                  <div class="fill-progress-text">
                    <span v-if="fillProgress.total > 0">{{ fillProgress.current }} / {{ fillProgress.total }} 点（{{ fillProgressPercentage }}%）</span>
                    <span v-else>正在准备...</span>
                  </div>
                </div>
              </template>

              <!-- 区域树 -->
              <template v-else>
                <div v-if="regionTreeLoading" v-loading="true" style="min-height: 60px"></div>
                <div v-else-if="regionTree.length > 0" class="region-tree-container">
                  <el-tree
                    :data="regionTree"
                    :props="{ label: 'name', children: 'children' }"
                    default-expand-all
                    :expand-on-click-node="false"
                    node-key="id"
                    :key="treeForceUpdateKey"
                    @node-click="handleRegionNodeClick"
                  >
                    <template #default="{ data }">
                      <div class="region-tree-node">
                        <div class="node-label">
                          <el-icon class="node-icon" :class="`icon-${data.type}`">
                            <LocationFilled v-if="data.type === 'province'" />
                            <LocationFilled v-else-if="data.type === 'city'" />
                            <LocationFilled v-else-if="data.type === 'district'" />
                            <Odometer v-else-if="data.type === 'road'" />
                          </el-icon>
                          <el-tag v-if="data.name === '未知区域'" type="danger" size="small">未知区域</el-tag>
                          <component v-else :is="() => renderNodeLabel(data)" />
                        </div>
                        <div class="node-info">
                          <span class="node-distance">{{ formatDistance(data.distance) }}</span>
                          <span v-if="data.start_time" class="node-time">{{ formatTimeRange(data.start_time, data.end_time) }}</span>
                        </div>
                      </div>
                    </template>
                  </el-tree>
                </div>
              </template>
            </el-card>

            <!-- 轨迹点列表
            <el-card class="points-card" shadow="never">
              <template #header>
                <span>轨迹点 ({{ points.length }})</span>
              </template>
              <el-scrollbar max-height="400">
                <div class="points-list">
                  <div
                    v-for="(point, index) in points"
                    :key="point.id"
                    class="point-item"
                    @click="highlightPoint(index)"
                    :class="{ highlighted: highlightedPointIndex === index }"
                  >
                    <div class="point-header">
                      <span class="point-index">#{{ point.point_index }}</span>
                      <span class="point-time">{{ formatTime(point.time) }}</span>
                    </div>
                    <div class="point-coords">
                      {{ point.latitude?.toFixed(6) }}, {{ point.longitude?.toFixed(6) }}
                    </div>
                    <div class="point-elevation" v-if="point.elevation">
                      海拔: {{ point.elevation.toFixed(1) }}m
                    </div>
                    <div class="point-location" v-if="point.city || point.road_name">
                      <el-tag v-if="point.city" size="mini">{{ point.city }}</el-tag>
                      <el-tag v-if="point.road_name" size="mini" type="success">{{ point.road_name }}</el-tag>
                    </div>
                  </div>
                </div>
              </el-scrollbar>
            </el-card> -->
          </div>
        </div>
      </template>
    </el-main>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑轨迹" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form :model="editForm" label-width="80px" class="dialog-form">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" placeholder="请输入轨迹名称" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入备注信息"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 下载对话框 -->
    <el-dialog v-model="downloadDialogVisible" title="下载 GPX" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form label-width="100px" class="dialog-form">
        <el-form-item label="坐标系">
          <el-radio-group v-model="downloadCRS">
            <el-radio value="original">原始 ({{ track?.original_crs?.toUpperCase() }})</el-radio>
            <el-radio value="wgs84">WGS84</el-radio>
            <el-radio value="gcj02">GCJ02 (火星)</el-radio>
            <el-radio value="bd09">BD09 (百度)</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="downloadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="downloadTrack">下载</el-button>
      </template>
    </el-dialog>

    <!-- 导出数据对话框 -->
    <el-dialog v-model="exportPointsDialogVisible" title="导出轨迹点数据" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form label-width="100px" class="dialog-form">
        <el-form-item label="文件格式">
          <el-radio-group v-model="exportFormat">
            <el-radio value="csv">CSV (Excel)</el-radio>
            <el-radio value="xlsx">XLSX (Excel)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-alert type="info" :closable="false" style="margin-top: 10px">
          导出后可以编辑地理信息，然后重新导入
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="exportPointsDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="exporting" @click="exportPoints">导出</el-button>
      </template>
    </el-dialog>

    <!-- 导入数据对话框 -->
    <el-dialog v-model="importDialogVisible" title="导入轨迹点数据" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form label-width="100px" class="dialog-form">
        <el-form-item label="匹配方式">
          <el-radio-group v-model="importMatchMode">
            <el-radio value="index">索引</el-radio>
            <el-radio value="time">时间</el-radio>
          </el-radio-group>
          <div class="radio-hint">
            <template v-if="importMatchMode === 'index'">
              匹配 index 列的值
            </template>
            <template v-else>
              匹配 time_date/time_time 或 time 列的值
            </template>
          </div>
        </el-form-item>
        <el-form-item v-if="importMatchMode === 'time'" label="文件时区">
          <el-select v-model="importTimezone" placeholder="选择导入文件的时间戳时区">
            <el-option label="UTC (世界标准时间)" value="UTC" />
            <el-option label="UTC+8 (北京时间)" value="UTC+8" />
            <el-option label="Asia/Shanghai (中国标准时间)" value="Asia/Shanghai" />
            <el-option label="UTC+1" value="UTC+1" />
            <el-option label="UTC+2" value="UTC+2" />
            <el-option label="UTC+3" value="UTC+3" />
            <el-option label="UTC+4" value="UTC+4" />
            <el-option label="UTC+5" value="UTC+5" />
            <el-option label="UTC+6" value="UTC+6" />
            <el-option label="UTC+7" value="UTC+7" />
            <el-option label="UTC+9" value="UTC+9" />
            <el-option label="UTC+10" value="UTC+10" />
            <el-option label="UTC-5" value="UTC-5" />
            <el-option label="UTC-6" value="UTC-6" />
            <el-option label="UTC-7" value="UTC-7" />
            <el-option label="UTC-8" value="UTC-8" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="importMatchMode === 'time'" label="时间误差">
          <el-input-number v-model="importTimeTolerance" :min="0.1" :max="60" :step="0.1" :precision="1" style="width: 150px" />
          <span style="margin-left: 8px; color: #999;">秒（不含边界值，如 1 表示 &lt; 1 秒）</span>
        </el-form-item>
        <el-form-item label="选择文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".csv,.xlsx"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-button type="primary">
              <el-icon><Upload /></el-icon>
              选择文件
            </el-button>
            <template #tip>
              <div style="font-size: 12px; color: #999; margin-top: 5px">
                支持 CSV 或 XLSX 格式
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-alert type="info" :closable="false" style="margin-top: 10px">
          导入将更新地理信息和备注，不会修改坐标和原始数据
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="importPoints" :disabled="!importFile">导入</el-button>
      </template>
    </el-dialog>

    <!-- 实时记录配置对话框 -->
    <el-dialog v-model="recordingDetailVisible" title="实时记录配置" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <div v-if="recordingDetail" class="recording-detail-content">
        <!-- 记录状态 -->
        <div class="recording-status">
          <div class="status-item">
            <span class="status-label">记录名称：</span>
            <span class="status-value">{{ recordingDetail.name }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">状态：</span>
            <el-tag v-if="recordingDetail.live_recording_status === 'active'" type="success" size="small">
              正在记录
            </el-tag>
            <el-tag v-else type="info" size="small">已结束</el-tag>
          </div>
        </div>

        <!-- 填充地理信息开关 -->
        <div class="setting-section">
          <div class="setting-item">
            <span class="setting-label">上传时自动填充地理信息</span>
            <el-switch
              v-model="recordingDetail.fill_geocoding"
              @change="updateRecordingFillGeocoding"
              :disabled="recordingDetail.live_recording_status !== 'active'"
            />
          </div>
          <div class="setting-tip">
            开启后，上传轨迹点时会自动获取省市区、道路名称等地理信息
          </div>
        </div>

        <!-- GPS Logger URL -->
        <div class="url-section">
          <div class="url-label">GPS Logger URL：</div>
          <el-input :model-value="recordingDetail.gpsLoggerUrl" readonly type="textarea" :rows="4" class="url-textarea" />
          <el-button @click="copyRecordingUrl" :icon="DocumentCopy" type="primary" class="copy-button">
            {{ recordingDetailCopyButtonText }}
          </el-button>
        </div>

        <!-- 二维码 -->
        <div class="qrcode-container" v-if="recordingDetail.qrCode">
          <div class="qrcode" v-html="recordingDetail.qrCode"></div>
          <p class="qrcode-tip">扫描二维码查看配置说明</p>
        </div>
      </div>

      <template #footer>
        <el-button @click="recordingDetailVisible = false">关闭</el-button>
        <el-button
          v-if="recordingDetail?.live_recording_status === 'active'"
          type="danger"
          @click="confirmEndRecording"
        >
          <el-icon><VideoPause /></el-icon>
          结束记录
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch, h } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'
import {
  ArrowLeft,
  Download,
  Upload,
  Edit,
  Document,
  Odometer,
  Clock,
  Top,
  Bottom,
  SuccessFilled,
  User,
  ArrowDown,
  Setting,
  SwitchButton,
  LocationFilled,
  Close,
  Link,
  DocumentCopy,
  VideoPause,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { trackApi, type Track, type TrackPoint, type FillProgressResponse, type RegionNode } from '@/api/track'
import { liveRecordingApi } from '@/api/liveRecording'
import UniversalMap from '@/components/map/UniversalMap.vue'
import QRCode from 'qrcode'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'
import { roadSignApi } from '@/api/roadSign'
import { parseRoadNumber, type ParsedRoadNumber } from '@/utils/roadSignParser'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const configStore = useConfigStore()

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value <= 1366)

// 响应式：判断是否为高屏（用于固定布局，仅电脑端）
const screenHeight = ref(window.innerHeight)
const isTallScreen = computed(() => !isMobile.value && screenHeight.value >= 800)

// 监听窗口大小变化
function handleResize() {
  screenWidth.value = window.innerWidth
  screenHeight.value = window.innerHeight
}

const loading = ref(true)
const track = ref<Track | null>(null)
const points = ref<TrackPoint[]>([])
const trackId = ref<number>(parseInt(route.params.id as string))
const highlightedPointIndex = ref<number>(-1)

const containerRef = ref<HTMLElement>()
const mapRef = ref()
const mapWrapperRef = ref<HTMLElement>()
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null  // 保存图表实例
let mapResizeObserver: ResizeObserver | null = null  // 地图容器大小监听器
const downloadDialogVisible = ref(false)
const downloadCRS = ref('original')

// 编辑相关
const editDialogVisible = ref(false)
const saving = ref(false)
const editForm = ref({
  name: '',
  description: ''
})

// 填充地理信息相关
const fillingGeocoding = ref(false)
const fillProgress = ref<{
  current: number
  total: number
  status: 'idle' | 'filling' | 'completed' | 'error' | 'stopped'
}>({ current: 0, total: 0, status: 'idle' })
let fillProgressTimer: number | null = null

// 区域树相关
const regionTree = ref<RegionNode[]>([])
const regionTreeLoading = ref(false)
const regionStats = ref<{ province: number; city: number; district: number; road: number }>({
  province: 0,
  city: 0,
  district: 0,
  road: 0,
})

// 道路标志 SVG 缓存：key 为 `${sign_type}:${code}`，value 为 SVG 字符串
const roadSignSvgCache = ref<Map<string, string>>(new Map())
// 正在加载的道路标志（防止重复加载）
const loadingSigns = ref<Set<string>>(new Set())
// 强制更新树组件的 key（当 SVG 加载完成后）
const treeForceUpdateKey = ref(0)

// 实时记录详情相关
const recordingDetailVisible = ref(false)
const recordingDetail = ref<{
  name: string
  live_recording_status: 'active' | 'ended'
  live_recording_id: number
  live_recording_token: string
  gpsLoggerUrl: string
  qrCode: string
  fill_geocoding: boolean
} | null>(null)
const recordingDetailCopyButtonText = ref('复制')

// 路径段高亮相关
const highlightedSegment = ref<{ start: number; end: number; nodeName: string } | null>(null)

// 导出相关
const exportPointsDialogVisible = ref(false)
const exportFormat = ref<'csv' | 'xlsx'>('csv')
const exporting = ref(false)

// 导入相关
const importDialogVisible = ref(false)
const importing = ref(false)
const importFile = ref<File | null>(null)
const importMatchMode = ref<'index' | 'time'>('index')
const importTimezone = ref<string>('UTC+8')
const importTimeTolerance = ref<number>(1.0)
const uploadRef = ref<UploadInstance>()

// 组合轨迹数据用于地图展示
const trackWithPoints = computed(() => {
  if (!track.value || !points.value.length) return null

  // 过滤出有有效坐标的点
  const validPoints = points.value.filter(p =>
    p.latitude_wgs84 != null &&
    p.longitude_wgs84 != null &&
    !isNaN(p.latitude_wgs84) &&
    !isNaN(p.longitude_wgs84)
  )

  if (validPoints.length === 0) return null

  return {
    id: track.value.id,
    points: validPoints.map(p => ({
      latitude: p.latitude_wgs84,
      longitude: p.longitude_wgs84,
      latitude_wgs84: p.latitude_wgs84,
      longitude_wgs84: p.longitude_wgs84,
      latitude_gcj02: p.latitude_gcj02,
      longitude_gcj02: p.longitude_gcj02,
      latitude_bd09: p.latitude_bd09,
      longitude_bd09: p.longitude_bd09,
      elevation: p.elevation,
      time: p.time,
      speed: p.speed,
      province: p.province,
      city: p.city,
      district: p.district,
      road_name: p.road_name,
      road_number: p.road_number,
    })),
  }
})

// 处理用户下拉菜单命令
function handleCommand(command: string) {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      authStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    })
  } else if (command === 'admin') {
    router.push('/admin')
  } else if (command === 'recordingDetail') {
    showRecordingDetail()
  } else if (command === 'edit') {
    showEditDialog()
  } else if (command === 'download') {
    downloadDialogVisible.value = true
  } else if (command === 'exportPoints') {
    exportPointsDialogVisible.value = true
  } else if (command === 'import') {
    importDialogVisible.value = true
  } else if (command === 'fill') {
    handleFillGeocoding()
  }
}

// 获取轨迹详情
async function fetchTrackDetail() {
  try {
    track.value = await trackApi.getDetail(trackId.value)
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 获取轨迹点
async function fetchTrackPoints() {
  try {
    const response = await trackApi.getPoints(trackId.value)
    points.value = response.points
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 获取区域树
async function fetchRegions() {
  if (!track.value?.has_area_info && !track.value?.has_road_info) {
    regionTree.value = []
    regionStats.value = { province: 0, city: 0, district: 0, road: 0 }
    return
  }

  try {
    regionTreeLoading.value = true
    const response = await trackApi.getRegions(trackId.value)
    regionTree.value = response.regions
    regionStats.value = response.stats
  } catch (error) {
    // 错误已在拦截器中处理
    regionTree.value = []
    regionStats.value = { province: 0, city: 0, district: 0, road: 0 }
  } finally {
    regionTreeLoading.value = false
  }
}

// 格式化节点显示名称
function formatNodeLabel(node: RegionNode): string {
  // 道路节点的特殊格式：道路编号在前，道路名称在后
  if (node.type === 'road' && node.road_number) {
    const roadNumbers = node.road_number.split(',').map(s => s.trim()).join(' / ')
    // 如果有道路名称且不是（无名），则道路编号 + 空格 + 道路名称
    if (node.name && node.name !== '（无名）') {
      return `${roadNumbers} ${node.name}`
    }
    // 只有道路编号
    return roadNumbers
  }
  // 非道路节点或没有道路编号，直接返回名称
  return node.name
}

// ========== 道路标志 SVG 相关 ==========

/**
 * 异步获取道路标志 SVG
 * @param code 道路编号，如 "S88"
 * @param sign_type 标志类型 'way' 或 'expwy'
 * @param province 省份简称（仅省级高速需要）
 * @returns SVG 字符串，失败返回 null
 */
async function getRoadSignSvg(code: string, signType: 'way' | 'expwy', province?: string): Promise<string | null> {
  // 缓存 key 包含省份（省级高速需要省份参数）
  const cacheKey = province ? `${signType}:${code}:${province}` : `${signType}:${code}`

  // 检查缓存
  const cached = roadSignSvgCache.value.get(cacheKey)
  if (cached) return cached

  try {
    const response = await roadSignApi.generate({
      sign_type: signType,
      code: code,
      ...(province && { province }),
    })
    const svg = response.svg
    roadSignSvgCache.value.set(cacheKey, svg)
    return svg
  } catch {
    // 生成失败，返回 null 使用文本回退
    return null
  }
}

/**
 * 异步加载单个道路编号的 SVG（不阻塞渲染）
 * @param parsed 解析后的道路编号信息
 */
async function loadRoadSignSvg(parsed: ParsedRoadNumber) {
  // 缓存 key 包含省份（省级高速需要）
  const key = parsed.province ? `${parsed.sign_type}:${parsed.code}:${parsed.province}` : `${parsed.sign_type}:${parsed.code}`

  // 防止重复加载
  if (loadingSigns.value.has(key)) {
    return
  }

  loadingSigns.value.add(key)

  try {
    const svg = await getRoadSignSvg(parsed.code, parsed.sign_type, parsed.province)
    if (svg) {
      // 触发树组件重新渲染
      treeForceUpdateKey.value++
    }
  } catch {
    // 生成失败，忽略错误
  } finally {
    loadingSigns.value.delete(key)
  }
}

/**
 * 渲染节点标签（支持 SVG 标牌）
 * 返回 VNode
 */
function renderNodeLabel(node: RegionNode) {
  const config = configStore.config
  const showSigns = config?.show_road_sign_in_region_tree ?? true

  // 处理道路节点且有道路编号
  if (node.type === 'road' && node.road_number) {
    const roadNumbers = node.road_number.split(',').map(s => s.trim())
    const contents: (string | ReturnType<typeof h>)[] = []

    if (showSigns) {
      // 开启标牌模式：尝试渲染 SVG
      roadNumbers.forEach((num, index) => {
        const parsed = parseRoadNumber(num)
        if (parsed) {
          const cacheKey = parsed.province ? `${parsed.sign_type}:${parsed.code}:${parsed.province}` : `${parsed.sign_type}:${parsed.code}`
          const svg = roadSignSvgCache.value.get(cacheKey)
          if (svg) {
            contents.push(h('span', { innerHTML: svg, class: 'road-sign-inline' }))
          } else {
            contents.push(num)
            loadRoadSignSvg(parsed)
          }
        } else {
          contents.push(num)
        }
        if (index < roadNumbers.length - 1) contents.push(' ')
      })
    } else {
      // 关闭标牌模式：显示纯文本编号
      contents.push(roadNumbers.join(' / '))
    }

    // 添加道路名称
    if (node.name && node.name !== '（无名）') {
      contents.push(' ')
      contents.push(node.name)
    }

    return h('span', contents)
  }

  // 非道路节点，使用原文本
  return h('span', node.name)
}

// 格式化距离
function formatDistance(meters: number): string {
  if (meters >= 1000) {
    const km = (meters / 1000).toFixed(2)
    // 去掉末尾的 .00
    return km.endsWith('.00') ? `${km.slice(0, -3)} km` : `${km} km`
  }
  return `${Math.round(meters)} m`
}

// 格式化时间范围
function formatTimeRange(start: string | null, end: string | null): string {
  if (!start) return '-'
  const startDate = new Date(start)
  const endDate = end ? new Date(end) : null

  // 格式化时间（本地时区）
  const formatTime = (date: Date) => {
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  }

  if (endDate) {
    const diff = (endDate.getTime() - startDate.getTime()) / 1000 / 60 // 分钟
    if (diff < 1) {
      return `${formatTime(startDate)}`
    } else if (diff < 60) {
      return `${formatTime(startDate)} - ${formatTime(endDate)} (${Math.round(diff)}分钟)`
    } else {
      const hours = Math.floor(diff / 60)
      const mins = Math.round(diff % 60)
      return `${formatTime(startDate)} - ${formatTime(endDate)} (${hours}小时${mins}分钟)`
    }
  }
  return formatTime(startDate)
}

// 处理区域节点点击（高亮对应路径段）
function handleRegionNodeClick(node: RegionNode) {
  if (node.start_index >= 0 && node.end_index >= 0) {
    highlightedSegment.value = {
      start: node.start_index,
      end: node.end_index,
      nodeName: node.name,
    }
    // 移动端：滚动到地图位置
    if (screenWidth.value <= 1366) {
      containerRef.value?.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }
}

// 清除路径段高亮
function clearSegmentHighlight() {
  highlightedSegment.value = null
}

// 渲染海拔和速度合并图表
function renderChart() {
  if (!chartRef.value || !points.value.length) return

  const chart = echarts.init(chartRef.value)
  chartInstance = chart  // 保存图表实例

  // 判断是否为移动端
  const isMobile = window.innerWidth <= 1366

  // 移动端数据采样
  let sampledPoints = points.value
  let sampledElevationData: number[][] = []
  let sampledSpeedData: number[][] = []
  let sampledXAxisData: string[] = []

  // if (isMobile && points.value.length > 100) {
  //   // 移动端使用采样：目标约 50 个点
  //   const targetPoints = 50
  //   const step = Math.ceil(points.value.length / targetPoints)
  //   sampledPoints = points.value.filter((_p: any, index: number) => index % step === 0)
  // }

  // 准备海拔数据
  sampledElevationData = sampledPoints
    .filter((p: any) => p.elevation !== null)
    .map((p: any, index: number) => [index, p.elevation])

  // 准备速度数据（转换为 km/h）
  sampledSpeedData = sampledPoints
    .filter((p: any) => p.speed !== null && p.speed !== undefined)
    .map((p: any, index: number) => [index, (p.speed ?? 0) * 3.6])

  // X 轴数据（使用时间标签）
  sampledXAxisData = sampledPoints.map((p: any, index: number) => {
    if (p.time) {
      const date = new Date(p.time)
      return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
    }
    return index.toString()
  })

  const option = {
    grid: {
      left: isMobile ? '30px' : '70px',
      right: isMobile ? '30px' : '70px',
      top: isMobile ? '30px' : '50px',
      bottom: isMobile ? '30px' : '50px',
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const dataIndex = params[0].dataIndex
        const point = sampledPoints[dataIndex]
        const speedRaw = point.speed
        const speedKmh = speedRaw !== null ? (speedRaw * 3.6).toFixed(2) : '-'
        let result = `点 #${dataIndex}<br/>时间: ${point.time ? formatTime(point.time) : '-'}<br/>`
        for (const param of params) {
          if (param.seriesName === '海拔') {
            const elevationValue = param.value !== null ? param.value.toFixed(1) : '-'
            result += `${param.marker}${param.seriesName}: ${elevationValue} m<br/>`
          } else if (param.seriesName === '速度') {
            result += `${param.marker}${param.seriesName}: ${speedKmh} km/h<br/>`
          }
        }
        return result
      },
    },
    xAxis: {
      type: 'category',
      data: sampledXAxisData,
      axisLabel: {
        interval: isMobile ? 'auto' : Math.max(1, Math.floor(sampledXAxisData.length / 10)),
        fontSize: isMobile ? 9 : 12,
        rotate: isMobile ? 45 : 0,
      },
      axisTick: {
        alignWithLabel: true,
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '海拔 (m)',
        nameLocation: 'middle',
        nameGap: isMobile ? 20 : 40,
        nameTextStyle: {
          padding: [0, 0, 0, 0],
          fontSize: isMobile ? 10 : 12,
        },
        axisLine: {
          lineStyle: {
            color: '#409eff',
          },
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: '#e5e5e5',
          },
        },
        splitNumber: isMobile ? 4 : 5,
        axisLabel: {
          fontSize: isMobile ? 9 : 12,
        },
      },
      {
        type: 'value',
        name: '速度 (km/h)',
        nameLocation: 'middle',
        nameGap: isMobile ? 20 : 40,
        nameTextStyle: {
          padding: [0, 0, 0, 0],
          fontSize: isMobile ? 10 : 12,
        },
        axisLine: {
          lineStyle: {
            color: '#67c23a',
          },
        },
        splitLine: {
          show: false,
        },
        splitNumber: isMobile ? 4 : 5,
        axisLabel: {
          fontSize: isMobile ? 9 : 12,
        },
      },
    ],
    series: [
      {
        name: '海拔',
        type: 'line',
        yAxisIndex: 0,
        data: sampledElevationData.map(d => d[1]),
        smooth: !isMobile, // 移动端不使用平滑
        sampling: null,
        symbol: 'none',
        areaStyle: isMobile ? undefined : {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.05)' },
            ],
          },
        },
        lineStyle: {
          color: '#409eff',
          width: 2,
        },
      },
      {
        name: '速度',
        type: 'line',
        yAxisIndex: 1,
        data: sampledSpeedData.map(d => d[1]),
        smooth: false,  // 禁用平滑，确保 tooltip 显示原始数据点值
        sampling: null,
        symbol: 'none',
        areaStyle: isMobile ? undefined : {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
              { offset: 1, color: 'rgba(103, 194, 58, 0.05)' },
            ],
          },
        },
        lineStyle: {
          color: '#67c23a',
          width: 2,
        },
      },
    ],
    legend: {
      data: ['海拔', '速度'],
      top: isMobile ? 5 : 10,
      right: 20,
      textStyle: {
        fontSize: isMobile ? 10 : 12,
      },
    },
  }

  chart.setOption(option)

  // 图表鼠标移动事件监听 - 用于反向同步到地图
  chart.on('mousemove', (params: any) => {
    // 检查是否在数据系列上
    if (params.componentType === 'series' && params.dataIndex !== undefined) {
      // 使用采样的原始索引（如果有采样数据）
      let originalIndex = params.dataIndex

      // 调用地图组件的 highlightPoint 方法
      if (mapRef.value?.highlightPoint) {
        mapRef.value.highlightPoint(originalIndex)
      }
    }
  })

  // 使用 axis 指针事件更可靠
  chart.on('showTip', (params: any) => {
    if (params.dataIndex !== undefined && mapRef.value?.highlightPoint) {
      mapRef.value.highlightPoint(params.dataIndex)
    }
  })

  // 图表鼠标离开事件 - 隐藏地图标记
  chart.on('mouseleave', () => {
    if (mapRef.value?.hideMarker) {
      mapRef.value.hideMarker()
    }
  })

  // 也监听 hideTip 事件
  chart.on('hideTip', () => {
    if (mapRef.value?.hideMarker) {
      mapRef.value.hideMarker()
    }
  })

  // 响应式调整
  const resizeObserver = new ResizeObserver(() => {
    chart.resize()
  })
  resizeObserver.observe(chartRef.value)
}

// 处理地图点悬浮事件 - 同步到图表
function handleMapPointHover(point: any, pointIndex: number) {
  if (!chartInstance || pointIndex < 0) return

  // 在图表上显示标记线
  chartInstance.dispatchAction({
    type: 'showTip',
    seriesIndex: 0,
    dataIndex: pointIndex,
  })

  // 高亮该点
  chartInstance.dispatchAction({
    type: 'highlight',
    seriesIndex: 0,
    dataIndex: pointIndex,
  })

  // 取消之前的高亮
  if (highlightedPointIndex.value >= 0 && highlightedPointIndex.value !== pointIndex) {
    chartInstance.dispatchAction({
      type: 'downplay',
      seriesIndex: 0,
      dataIndex: highlightedPointIndex.value,
    })
  }

  highlightedPointIndex.value = pointIndex
}

// 填充地理信息
async function handleFillGeocoding() {
  // 如果已经填充过，显示确认对话框
  if (track.value?.has_area_info || track.value?.has_road_info) {
    try {
      await ElMessageBox.confirm(
        '已填充地理信息，再次填充会覆盖已有的信息，是否继续？',
        '确认重新填充',
        {
          confirmButtonText: '继续',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
    } catch {
      // 用户点击取消
      return
    }
  }

  try {
    await trackApi.fillGeocoding(trackId.value)
    ElMessage.success('开始填充地理信息')
    fillingGeocoding.value = true
    startPollingProgress()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 停止填充地理信息
async function handleStopFillGeocoding() {
  try {
    await trackApi.stopFillGeocoding(trackId.value)
    ElMessage.info('已停止填充')
    stopPollingProgress()
    fillingGeocoding.value = false
    // 重新加载进度状态
    const response = await trackApi.getFillProgress(trackId.value)
    fillProgress.value = response.progress
  } catch (error) {
    console.error('Stop fill error:', error)
  }
}

// 开始轮询进度
function startPollingProgress() {
  if (fillProgressTimer) return

  fillProgressTimer = window.setInterval(async () => {
    try {
      const response = await trackApi.getFillProgress(trackId.value)
      fillProgress.value = response.progress

      if (response.progress.status === 'completed') {
        stopPollingProgress()
        fillingGeocoding.value = false
        ElMessage.success('地理信息填充完成')
        // 重新加载轨迹数据
        await fetchTrackDetail()
        await fetchTrackPoints()
        await fetchRegions()
      } else if (response.progress.status === 'error') {
        stopPollingProgress()
        fillingGeocoding.value = false
        ElMessage.error('填充地理信息失败')
      } else if (response.progress.status === 'stopped') {
        stopPollingProgress()
        fillingGeocoding.value = false
        ElMessage.info('填充已停止')
      }
    } catch (error) {
      console.error('Failed to fetch fill progress:', error)
    }
  }, 2000)
}

// 停止轮询进度
function stopPollingProgress() {
  if (fillProgressTimer) {
    clearInterval(fillProgressTimer)
    fillProgressTimer = null
  }
}

// 填充进度百分比
const fillProgressPercentage = computed(() => {
  if (fillProgress.value.total > 0) {
    return Math.round((fillProgress.value.current / fillProgress.value.total) * 100)
  }
  return 0
})

// 获取填充进度百分比
function getFillProgressPercentage(): number {
  if (fillProgress.value.total > 0) {
    return Math.round((fillProgress.value.current / fillProgress.value.total) * 100)
  }
  return 0
}

// 检查并恢复填充进度轮询
async function checkAndResumeFilling() {
  try {
    const response = await trackApi.getFillProgress(trackId.value)
    fillProgress.value = response.progress

    // 如果正在填充，启动轮询
    if (response.progress.status === 'filling') {
      fillingGeocoding.value = true
      startPollingProgress()
    }
  } catch (error) {
    // 忽略错误，可能是填充功能还未调用过
  }
}

// 高亮点
function highlightPoint(index: number) {
  highlightedPointIndex.value = index
  // TODO: 在地图上高亮该点
}

// 显示下载对话框
function showDownloadDialog() {
  downloadDialogVisible.value = true
}

// 显示实时记录详情对话框
async function showRecordingDetail() {
  if (!track.value?.live_recording_id) return

  try {
    // 从后端获取最新的实时记录数据（包含 fill_geocoding）
    const recording = await liveRecordingApi.getList('active')
    const currentRecording = recording.find(r => r.id === track.value?.live_recording_id)

    if (!currentRecording) {
      ElMessage.error('找不到实时记录')
      return
    }

    const gpsLoggerUrl = liveRecordingApi.getGpsLoggerUrl(currentRecording.token)

    // 生成二维码
    const qrCode = await QRCode.toString(gpsLoggerUrl, {
      width: 200,
      margin: 2,
      type: 'svg',
    })

    recordingDetail.value = {
      name: track.value.name,
      live_recording_status: currentRecording.status,
      live_recording_id: currentRecording.id,
      live_recording_token: currentRecording.token,
      gpsLoggerUrl,
      qrCode,
      fill_geocoding: currentRecording.fill_geocoding || false,
    }
    recordingDetailVisible.value = true
  } catch (error) {
    ElMessage.error('获取实时记录信息失败')
  }
}

// 复制实时记录 URL
function copyRecordingUrl() {
  if (!recordingDetail.value) return
  const url = recordingDetail.value.gpsLoggerUrl

  // 检查剪贴板 API 是否可用
  if (!navigator.clipboard) {
    const textarea = document.createElement('textarea')
    textarea.value = url
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()

    try {
      const successful = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (successful) {
        recordingDetailCopyButtonText.value = '已复制'
        ElMessage.success('URL 已复制到剪贴板')
        setTimeout(() => {
          recordingDetailCopyButtonText.value = '复制'
        }, 2000)
      } else {
        ElMessage.error('复制失败，请手动选择复制')
      }
    } catch (err) {
      document.body.removeChild(textarea)
      ElMessage.error('复制失败，请手动选择复制')
      console.error('复制失败:', err)
    }
    return
  }

  navigator.clipboard.writeText(url).then(() => {
    recordingDetailCopyButtonText.value = '已复制'
    ElMessage.success('URL 已复制到剪贴板')
    setTimeout(() => {
      recordingDetailCopyButtonText.value = '复制'
    }, 2000)
  }).catch((err) => {
    const isSecureContext = window.isSecureContext
    if (!isSecureContext) {
      ElMessage.warning('剪贴板 API 需要 HTTPS 环境，请手动选择复制')
    } else {
      ElMessage.error('复制失败，请手动复制')
    }
    console.error('复制失败:', err)
  })
}

// 更新填充地理信息设置
async function updateRecordingFillGeocoding(value: boolean) {
  if (!recordingDetail.value?.live_recording_id) return

  const originalValue = recordingDetail.value.fill_geocoding

  try {
    await liveRecordingApi.updateFillGeocoding(recordingDetail.value.live_recording_id, value)
    // 成功后更新本地状态
    recordingDetail.value.fill_geocoding = value
    // 同时更新 track 的 fill_geocoding 值（如果存在）
    if (track.value) {
      track.value.fill_geocoding = value
    }
    ElMessage.success(value ? '已开启自动填充地理信息' : '已关闭自动填充地理信息')
  } catch (error) {
    // 失败时恢复到原来的值
    recordingDetail.value.fill_geocoding = originalValue
    console.error('更新填充地理信息设置失败:', error)
  }
}

// 结束实时记录（带二次确认）
async function confirmEndRecording() {
  if (!recordingDetail.value) return

  try {
    await ElMessageBox.confirm(
      `确定要结束实时记录"${recordingDetail.value.name}"吗？结束后将无法继续上传轨迹点。`,
      '确认结束记录',
      {
        confirmButtonText: '确定结束',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await liveRecordingApi.end(recordingDetail.value.live_recording_id)
    ElMessage.success('记录已结束')
    recordingDetailVisible.value = false
    // 重新加载轨迹数据
    await fetchTrackDetail()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 显示编辑对话框
function showEditDialog() {
  if (track.value) {
    editForm.value.name = track.value.name
    editForm.value.description = track.value.description || ''
  }
  editDialogVisible.value = true
}

// 保存编辑
async function saveEdit() {
  if (!track.value) return

  if (!editForm.value.name.trim()) {
    ElMessage.warning('轨迹名称不能为空')
    return
  }

  saving.value = true
  try {
    const updated = await trackApi.update(track.value.id, {
      name: editForm.value.name.trim(),
      description: editForm.value.description.trim() || undefined
    })
    track.value = updated
    editDialogVisible.value = false
    ElMessage.success('保存成功')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
  }
}

// 下载轨迹
async function downloadTrack() {
  try {
    const url = trackApi.download(trackId.value, downloadCRS.value)
    // 使用 fetch 下载，自动携带认证信息
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (!response.ok) {
      throw new Error('下载失败')
    }

    // 获取文件名
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = `track_${trackId.value}.gpx`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="(.+)"/)
      if (match) filename = match[1]
    }

    // 创建 blob 并下载
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)

    downloadDialogVisible.value = false
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('Download error:', error)
    ElMessage.error('下载失败')
  }
}

// 导出轨迹点
async function exportPoints() {
  try {
    exporting.value = true
    const url = trackApi.exportPoints(trackId.value, exportFormat.value)
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (!response.ok) {
      throw new Error('导出失败')
    }

    // 获取文件名
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = `track_${trackId.value}_points.${exportFormat.value}`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="(.+)"/)
      if (match) filename = match[1]
    }

    // 创建 blob 并下载
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)

    exportPointsDialogVisible.value = false
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('Export error:', error)
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// 处理文件选择
function handleFileChange(file: UploadFile) {
  if (file.raw) {
    importFile.value = file.raw
  }
}

// 处理文件移除
function handleFileRemove() {
  importFile.value = null
}

// 导入轨迹点
async function importPoints() {
  if (!importFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  try {
    importing.value = true
    const result = await trackApi.importPoints(trackId.value, importFile.value, importMatchMode.value, importTimezone.value, importTimeTolerance.value)

    const matchMsg = result.matched_by === 'time' ? '（通过时间匹配）' : '（通过索引匹配）'
    ElMessage.success(`导入成功！更新了 ${result.updated} 个点，共 ${result.total} 个点 ${matchMsg}`)

    importDialogVisible.value = false
    importFile.value = null
    if (uploadRef.value) {
      uploadRef.value.clearFiles()
    }

    // 重新加载轨迹数据
    await fetchTrackDetail()
    await fetchTrackPoints()
    await fetchRegions()
  } catch (error) {
    console.error('Import error:', error)
    ElMessage.error('导入失败，请检查文件格式是否正确')
  } finally {
    importing.value = false
  }
}

// 格式化函数
function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function formatElevation(meters: number): string {
  return `${meters.toFixed(0)} m`
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatTimeOnly(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
}

// 判断两个日期是否为同一天（本地时区）
function isSameDay(dateStr1: string | null, dateStr2: string | null): boolean {
  if (!dateStr1 || !dateStr2) return false
  const date1 = new Date(dateStr1)
  const date2 = new Date(dateStr2)
  return date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
}

onMounted(async () => {
  try {
    await fetchTrackDetail()
    await fetchTrackPoints()
    await fetchRegions()
  } catch (error) {
    console.error('Failed to load track data:', error)
  } finally {
    loading.value = false
  }

  // 检查是否有正在进行的填充操作
  await checkAndResumeFilling()

  // 等待 DOM 更新后渲染图表
  nextTick(() => {
    renderChart()

    // 为地图容器添加 ResizeObserver（在固定布局中响应容器大小变化）
    if (mapWrapperRef.value) {
      mapResizeObserver = new ResizeObserver(() => {
        if (mapRef.value?.resize) {
          mapRef.value.resize()
        }
      })
      mapResizeObserver.observe(mapWrapperRef.value)
    }
  })

  // 添加窗口大小监听
  window.addEventListener('resize', handleResize)
})

// 监听布局切换，重新渲染图表
watch(isTallScreen, () => {
  nextTick(() => {
    renderChart()
  })
})

onUnmounted(() => {
  stopPollingProgress()

  // 清理地图 ResizeObserver
  if (mapResizeObserver) {
    mapResizeObserver.disconnect()
    mapResizeObserver = null
  }

  // 移除窗口大小监听器
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.track-detail-container {
  height: 100vh;
  overflow-y: auto;
  background: #f5f7fa;
  display: block;
}

.track-detail-container > .el-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  gap: 16px;
  flex-shrink: 0;
}

.track-detail-container > .el-main {
  overflow: visible;
}

/* 限制地图相关元素的 z-index */
.map-card {
  position: relative;
  z-index: 1;
}

/* 常规布局地图容器 */
.normal-map-container {
  height: 40vh;
  min-height: 300px;
  position: relative;
}

:deep(.leaflet-map-container) {
  z-index: 1;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
}

.title-with-tags {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.title-tag {
  flex-shrink: 0;
}

.header-left h1 {
  font-size: 20px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  padding: 5px 10px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.user-info .username {
  display: inline;
}

.desktop-only {
  display: inline-block;
}

.main {
  max-width: 1600px;
  margin: 0 auto;
  padding: 20px;
  width: 100%;
}

.map-card,
.chart-card {
  margin-bottom: 20px;
}

.map-card :deep(.el-card__body) {
  padding: 0;
  height: 500px;
}

.map-placeholder {
  height: 500px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  text-align: center;
}

.map-placeholder p {
  margin: 8px 0;
}

.debug-info {
  font-size: 12px;
  color: #f56c6c;
}

.stats-card,
.info-card,
.areas-card,
.points-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.stats-card :deep(.el-row) {
  --el-row-gutter: 20px;
}

.stats-card :deep(.el-col) {
  margin-top: 8px;
  margin-bottom: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  font-size: 24px;
}

.stat-value {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 12px;
  color: #999;
}

/* 起止时间样式 */
.time-range-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
}

.time-range-item {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}

.time-range-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-height: 36px;
  justify-content: center;
}

.time-range-time {
  font-size: 18px;
  font-weight: bold;
  color: #333;
  line-height: 1.2;
}

.time-range-date {
  font-size: 12px;
  color: #999;
  line-height: 1.2;
}

.time-range-divider {
  position: relative;
  flex: 1;
  height: 1px;
  background: #e4e4e7;
  margin: 0 16px;
}

.time-range-divider-icon {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  font-size: 14px;
  color: #999;
  background: white;
  padding: 0 4px;
}

.time-range-divider-date {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  color: #999;
  background: white;
  padding: 0 8px;
  white-space: nowrap;
}

/* 同一天时隐藏两边日期 */
.time-range-section.same-day .time-range-date {
  display: none;
}

/* 备注样式 */
.description-section {
  margin-top: 8px;
}

.description-section .description-text {
  color: #606266;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
}

.chart {
  height: 22vh;
  min-height: 180px;
}

/* 时间线样式 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 区域树样式 */
.region-tree-container {
  padding: 10px 0;
}

.region-tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 10px;
}

.node-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  font-size: 16px;
}

.node-icon.icon-province {
  color: #f56c6c;
}

.node-icon.icon-city {
  color: #409eff;
}

.node-icon.icon-district {
  color: #67c23a;
}

.node-icon.icon-road {
  color: #e6a23c;
}

.node-name {
  font-weight: 500;
  color: #303133;
}

/* 行内道路标志 SVG */
.road-sign-inline {
  display: inline-block;
  vertical-align: middle;
  line-height: 1;
  margin: 0 1px;
}

.road-sign-inline :deep(svg) {
  display: inline-block;
  vertical-align: middle;
  height: 1em;
  width: auto;
}

.node-info {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #909399;
  font-size: 12px;
}

.node-distance {
  color: #606266;
  font-weight: 500;
}

.node-time {
  color: #909399;
}

/* 未填充提示 */
.no-fill-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 20px;
  color: #909399;
}

.no-fill-hint .el-icon {
  font-size: 48px;
  color: #c0c4cc;
}

.no-fill-hint span {
  font-size: 14px;
}

.no-fill-actions {
  display: flex;
  gap: 12px;
}

/* 填充进度 */
.fill-progress-section {
  padding: 20px;
}

.fill-progress-hint {
  font-size: 14px;
  color: #409eff;
  margin-bottom: 12px;
}

.fill-progress-with-action {
  display: flex;
  align-items: center;
  gap: 12px;
}

.fill-progress-with-action :deep(.el-progress) {
  flex: 1;
}

.stop-fill-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  position: relative;
}

.stop-fill-btn::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 10px;
  height: 10px;
  background-color: currentColor;
}

.fill-progress-text {
  text-align: left;
  margin-top: 10px;
  font-size: 13px;
  color: #606266;
}

.info-missing {
  color: #f56c6c;
  font-size: 12px;
  font-style: italic;
}

.points-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.point-item {
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.point-item:hover {
  background: #f5f7fa;
}

.point-item.highlighted {
  background: #e6f7ff;
  border-color: #409eff;
}

.point-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.point-index {
  font-weight: bold;
  color: #409eff;
}

.point-time {
  font-size: 12px;
  color: #999;
}

.point-coords {
  font-size: 12px;
  color: #666;
  margin-bottom: 2px;
}

.point-elevation {
  font-size: 12px;
  color: #666;
}

.point-location {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.fill-progress-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.fill-progress-bar {
  margin-top: 4px;
}

.fill-progress-text {
  font-size: 12px;
  color: #909399;
  text-align: left;
  margin-top: 4px;
}

.fill-status-text {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

/* 单选按钮说明文字 */
.radio-hint {
  display: block;
  width: 100%;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 12px;
  line-height: 1.5;
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .el-header {
    flex-wrap: wrap;
    padding: 10px;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .header-left h1 {
    font-size: 16px;
  }

  .desktop-only {
    display: none !important;
  }

  .user-info .username {
    display: inline;
  }

  .main {
    padding: 10px;
    height: auto !important;
    overflow: visible !important;
  }

  .main-fixed {
    padding: 10px !important;
    height: auto !important;
    overflow: visible !important;
  }

  .map-card :deep(.el-card__body),
  .map-placeholder {
    height: calc(30vh);
    min-height: 200px;
  }

  .chart {
    height: calc(20vh);
    min-height: 150px;
  }

  .stat-icon {
    font-size: 20px;
  }

  .stat-value {
    font-size: 16px;
  }

  .stat-label {
    font-size: 11px;
  }

  .time-range-section {
    gap: 8px;
  }

  .time-range-item {
    width: 100%;
  }

  .time-range-time {
    font-size: 16px;
  }

  .time-range-date {
    font-size: 11px;
  }

  .time-range-divider {
    margin: 0 8px;
  }

  /* 移动端保持流式布局，整个页面可滚动 */
  .normal-layout {
    flex-direction: column;
    height: auto;
    display: block;
  }

  .normal-left,
  .normal-right {
    width: 100%;
    overflow: visible;
    padding: 0;
  }

  .normal-left > *,
  .normal-right > * {
    margin-bottom: 15px;
  }

  /* 固定布局改为单列流式 */
  .fixed-layout {
    flex-direction: column;
    height: auto;
    display: block;
  }

  .fixed-left {
    width: 100%;
    height: auto;
    overflow: visible;
    flex: none;
  }

  .fixed-left .map-card {
    flex: none;
    margin-bottom: 15px;
  }

  .fixed-left .map-card :deep(.el-card__body) {
    height: auto;
  }

  .map-wrapper {
    height: 30vh;
    min-height: 200px;
  }

  .scrollable-right {
    width: 100%;
    overflow: visible;
    padding: 0;
  }
}

/* 固定布局样式（高屏 >= 800px） */
.main-fixed {
  padding: 20px !important;
  height: calc(100vh - 60px); /* 减去导航栏高度 */
  overflow: hidden !important;
}

.fixed-layout {
  display: flex;
  gap: 20px;
  height: 100%;
}

.fixed-left {
  flex: 0 0 calc(66.666% - 10px);
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
  overflow: hidden;
}

.fixed-left .map-card {
  flex: 1;
  margin-bottom: 0;
  display: flex;
  flex-direction: column;
}

.fixed-left .map-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  height: auto;
}

.map-wrapper {
  height: 100%;
  position: relative;
}

.fixed-left .chart-card {
  flex: 0 0 auto;
  margin-bottom: 0;
}

.scrollable-right {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 5px;
}

/* 滚动条样式优化 */
.scrollable-right::-webkit-scrollbar {
  width: 6px;
}

.scrollable-right::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.scrollable-right::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.scrollable-right::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.scrollable-right .stats-card,
.scrollable-right .info-card,
.scrollable-right .areas-card {
  margin-bottom: 20px;
}

/* 常规布局样式（仅电脑端高度 < 800px 时使用独立滚动） */
@media (min-width: 1367px) {
  .normal-layout {
    display: flex;
    gap: 20px;
    height: calc(100vh - 100px);
  }

  .normal-left {
    flex: 0 0 calc(66.666% - 10px);
    direction: rtl;
    overflow-y: auto;
    overflow-x: hidden;
    padding-left: 5px;
  }

  .normal-left > * {
    direction: ltr;
  }

  .normal-left::-webkit-scrollbar {
    width: 6px;
  }

  .normal-left::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
  }

  .normal-left::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;
  }

  .normal-left::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8;
  }

  .normal-right {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 5px;
  }

  .normal-right::-webkit-scrollbar {
    width: 6px;
  }

  .normal-right::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
  }

  .normal-right::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;
  }

  .normal-right::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8;
  }

  .normal-right .stats-card,
  .normal-right .info-card,
  .normal-right .areas-card {
    margin-bottom: 20px;
  }

  /* 对话框移动端样式 */
  .responsive-dialog {
    width: 95% !important;
  }

  .responsive-dialog .el-dialog__body {
    max-height: 60vh;
    overflow-y: auto;
  }

  .dialog-form :deep(.el-form-item__label) {
    width: 80px !important;
    font-size: 14px;
  }
}

/* 实时记录详情对话框 */
.recording-detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.recording-status {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-label {
  font-weight: 500;
  color: var(--el-text-color-regular);
  min-width: 80px;
}

.status-value {
  color: var(--el-text-color-primary);
}

.url-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.url-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.url-textarea {
  font-family: monospace;
}

.copy-button {
  align-self: flex-start;
}

/* 设置区域 */
.setting-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.setting-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.setting-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: 0;
}

.qrcode-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.qrcode {
  display: flex;
}

.qrcode :deep(svg) {
  width: 200px;
  height: 200px;
}

.qrcode-tip {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>

<style>
/* 全局样式：道路标志 SVG 高度控制 */
.road-sign-inline svg {
  display: inline-block;
  vertical-align: middle;
  height: 1.4em;
  width: auto;
}
</style>
