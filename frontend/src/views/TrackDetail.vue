<template>
  <div ref="containerRef" class="track-detail-container">
    <el-header>
      <div class="header-left">
        <el-button @click="$router.back()" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="$router.push('/home')" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <div class="title-with-tags">
          <!-- 实时记录状态指示器 -->
          <el-tooltip
            v-if="track?.is_live_recording && track.live_recording_status === 'active'"
            content="实时轨迹记录中"
            placement="bottom"
          >
            <span class="live-status-indicator status-recording"></span>
          </el-tooltip>
          <!-- 实时更新状态指示器 -->
          <el-tooltip
            v-if="isLiveUpdating && liveUpdateStatus !== 'connected'"
            :content="liveUpdateStatus === 'connected' ? '实时更新中' : '连接断开'"
            placement="bottom"
          >
            <span
              class="live-status-indicator"
              :class="{
                'status-error': liveUpdateStatus === 'error' || liveUpdateStatus === 'disconnected'
              }"
            ></span>
          </el-tooltip>
          <h1>{{ track?.name || '轨迹详情' }}</h1>
        </div>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <el-button
            v-if="track?.is_live_recording && track.live_recording_token && track.live_recording_status === 'active'"
            type="warning"
            @click="showRecordingDetail"
            class="desktop-only"
          >
            <el-icon><Link /></el-icon>
            记录配置
          </el-button>
          <!-- 编辑轨迹下拉菜单 -->
          <el-dropdown @command="handleEditCommand" trigger="click" class="desktop-only">
            <el-button type="primary">
              编辑轨迹
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="geo-editor">
                  <el-icon><Edit /></el-icon>
                  编辑地理信息
                </el-dropdown-item>
                <el-dropdown-item command="interpolation">
                  <el-icon><Link /></el-icon>
                  路径插值
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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
          <el-button type="primary" @click="posterDialogVisible = true" class="desktop-only">
            <el-icon><Picture /></el-icon>
            导出海报
          </el-button>
          <el-button type="primary" @click="overlayExportDialogVisible = true" class="desktop-only">
            <el-icon><Film /></el-icon>
            覆盖层
          </el-button>
          <el-button type="primary" @click="shareDialogVisible = true" class="desktop-only">
            <el-icon><Share /></el-icon>
            分享
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
                v-if="isMobile && track?.is_live_recording && track.live_recording_token && track.live_recording_status === 'active'"
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
              <el-dropdown-item command="poster" v-if="isMobile">
                <el-icon><Picture /></el-icon>
                导出海报
              </el-dropdown-item>
              <el-dropdown-item command="overlayExport" v-if="isMobile">
                <el-icon><Film /></el-icon>
                覆盖层
              </el-dropdown-item>
              <el-dropdown-item command="share" v-if="isMobile">
                <el-icon><Share /></el-icon>
                分享
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

    <el-main class="main" :class="{ 'main-fixed': isTallScreen }">
      <!-- 加载中显示骨架屏 -->
      <div v-if="loading" class="detail-skeleton">
        <!-- 固定布局骨架屏 -->
        <template v-if="isTallScreen">
          <div class="fixed-layout">
            <div class="fixed-left">
              <el-card class="map-card" shadow="never">
                <div class="card-skeleton-wrapper">
                  <el-skeleton :rows="1" animated />
                </div>
                <div class="map-skeleton-content">
                  <el-skeleton :rows="8" animated />
                </div>
              </el-card>
              <el-card class="chart-card" shadow="never">
                <div class="card-skeleton-wrapper">
                  <el-skeleton :rows="1" animated />
                </div>
                <div class="chart-skeleton-content">
                  <el-skeleton :rows="4" animated />
                </div>
              </el-card>
            </div>
            <div class="scrollable-right">
              <el-card class="stats-card" shadow="never">
                <div class="card-skeleton-wrapper">
                  <el-skeleton :rows="6" animated />
                </div>
              </el-card>
            </div>
          </div>
        </template>
        <!-- 常规布局骨架屏 -->
        <template v-else>
          <el-row :gutter="20">
            <el-col :xs="24" :md="16">
              <el-card class="map-card" shadow="never">
                <div class="card-skeleton-wrapper">
                  <el-skeleton :rows="1" animated />
                </div>
                <div class="map-skeleton-content">
                  <el-skeleton :rows="6" animated />
                </div>
              </el-card>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-card class="stats-card" shadow="never">
                <div class="card-skeleton-wrapper">
                  <el-skeleton :rows="8" animated />
                </div>
              </el-card>
            </el-col>
          </el-row>
          <el-row :gutter="20" style="margin-top: 20px">
            <el-col :xs="24" :md="16">
              <el-card class="chart-card" shadow="never">
                <div class="card-skeleton-wrapper">
                  <el-skeleton :rows="1" animated />
                </div>
                <div class="chart-skeleton-content">
                  <el-skeleton :rows="4" animated />
                </div>
              </el-card>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-card class="regions-card" shadow="never">
                <div class="card-skeleton-wrapper">
                  <el-skeleton :rows="6" animated />
                </div>
              </el-card>
            </el-col>
          </el-row>
        </template>
      </div>

      <!-- 加载失败时显示错误提示 -->
      <el-alert v-else-if="loadFailed && !track" type="error" :closable="false" style="margin-bottom: 20px">
        轨迹数据加载失败，请返回列表重试
      </el-alert>

      <!-- 加载完成后显示内容 -->
      <template v-else>
        <template v-if="track">
        <!-- 固定布局容器（高屏时使用） -->
        <div v-if="isTallScreen" class="fixed-layout">
          <!-- 左侧固定区域 -->
          <div class="fixed-left">
            <!-- 地图 -->
            <el-card class="map-card" shadow="never">
              <template v-if="trackWithPoints">
                <div ref="mapWrapperRef" class="map-wrapper">
                  <div ref="mapElementRef" class="map-content">
                    <!-- 动画播放器 -->
                    <TrackAnimationPlayer
                      v-if="animationConfig"
                      :config="animationConfig"
                      :track-id="track.id"
                      :map-provider="mapProvider"
                    />
                    <UniversalMap
                      ref="mapRef"
                      :tracks="[trackWithPoints]"
                      :highlight-track-id="track.id"
                      :highlight-segments="highlightedSegment ? [highlightedSegment] : null"
                      :latest-point-index="latestPointIndex"
                      :live-update-time="track.live_recording_status === 'active' ? (track.last_point_created_at || track.last_upload_at) : null"
                      :enable-animation="true"
                      @point-hover="handleMapPointHover"
                      @clear-segment-highlight="clearSegmentHighlight"
                      @map-provider-changed="handleMapProviderChanged"
                  />
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="map-placeholder">
                  <p v-if="isWaitingForPoints">等待记录中...</p>
                  <p v-else>{{ points.length === 0 ? '正在加载轨迹点数据...' : '轨迹点坐标数据无效' }}</p>
                  <p v-if="points.length > 0 && !isWaitingForPoints" class="debug-info">
                    轨迹点数量: {{ points.length }}，
                    有效坐标: {{ points.filter(p => p.latitude_wgs84 != null && p.longitude_wgs84 != null).length }}
                  </p>
                  <el-button v-if="!isWaitingForPoints" size="small" @click="$router.push('/upload')">上传新轨迹</el-button>
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
                  <!-- 待记录状态 -->
                  <div v-if="isWaitingForPoints" class="waiting-for-points">
                    <el-icon class="waiting-icon"><Clock /></el-icon>
                    <p class="waiting-text">等待记录中...</p>
                    <p class="waiting-hint">请使用 GPS Logger 等应用上传轨迹点</p>
                  </div>
                  <!-- 正常统计信息 -->
                  <template v-else>
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
                  </template>
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
                        <span v-if="fillProgress.total > 0">
                          <template v-if="(fillProgress.current + fillProgress.failed) > 0 && fillProgress.failed > 0">
                            {{ fillProgress.current }} <span class="fill-failed-count">+ {{ fillProgress.failed }} 失败</span> / {{ fillProgress.total }} 点（{{ fillProgressPercentage }}%）
                          </template>
                          <template v-else>
                            {{ fillProgress.current }} / {{ fillProgress.total }} 点（{{ fillProgressPercentage }}%）
                          </template>
                        </span>
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
                              <el-icon v-if="(data.original_type || data.type) !== 'road'" class="node-icon" :class="`icon-${data.original_type || data.type}`">
                                <LocationFilled v-if="(data.original_type || data.type) === 'province'" />
                                <LocationFilled v-else-if="(data.original_type || data.type) === 'city'" />
                                <LocationFilled v-else-if="(data.original_type || data.type) === 'district'" />
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
                <div ref="mapElementRef" class="normal-map-container">
                  <UniversalMap
                    ref="mapRef"
                    :tracks="[trackWithPoints]"
                    :highlight-track-id="track.id"
                    :highlight-segments="highlightedSegment ? [highlightedSegment] : null"
                    :latest-point-index="latestPointIndex"
                    :live-update-time="track.live_recording_status === 'active' ? (track.last_point_created_at || track.last_upload_at) : null"
                    :enable-animation="true"
                    @point-hover="handleMapPointHover"
                    @clear-segment-highlight="clearSegmentHighlight"
                  />
                </div>
              </template>
              <template v-else>
                <div class="map-placeholder">
                  <p v-if="isWaitingForPoints">等待记录中...</p>
                  <p v-else>{{ points.length === 0 ? '正在加载轨迹点数据...' : '轨迹点坐标数据无效' }}</p>
                  <p v-if="points.length > 0 && !isWaitingForPoints" class="debug-info">
                    轨迹点数量: {{ points.length }}，
                    有效坐标: {{ points.filter(p => p.latitude_wgs84 != null && p.longitude_wgs84 != null).length }}
                  </p>
                  <el-button v-if="!isWaitingForPoints" size="small" @click="$router.push('/upload')">上传新轨迹</el-button>
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
              <!-- 待记录状态 -->
              <div v-if="isWaitingForPoints" class="waiting-for-points">
                <el-icon class="waiting-icon"><Clock /></el-icon>
                <p class="waiting-text">等待记录中...</p>
                <p class="waiting-hint">请使用 GPS Logger 等应用上传轨迹点</p>
              </div>
              <!-- 正常统计信息 -->
              <template v-else>
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
              </template>
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
                    <span v-if="fillProgress.total > 0">
                      <template v-if="(fillProgress.current + fillProgress.failed) > 0 && fillProgress.failed > 0">
                        {{ fillProgress.current }} <span class="fill-failed-count">+ {{ fillProgress.failed }} 失败</span> / {{ fillProgress.total }} 点（{{ fillProgressPercentage }}%）
                      </template>
                      <template v-else>
                        {{ fillProgress.current }} / {{ fillProgress.total }} 点（{{ fillProgressPercentage }}%）
                      </template>
                    </span>
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
                          <el-icon v-if="(data.original_type || data.type) !== 'road'" class="node-icon" :class="`icon-${data.original_type || data.type}`">
                            <LocationFilled v-if="(data.original_type || data.type) === 'province'" />
                            <LocationFilled v-else-if="(data.original_type || data.type) === 'city'" />
                            <LocationFilled v-else-if="(data.original_type || data.type) === 'district'" />
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
                      <span class="point-index">#{{ index + 1 }}</span>
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
      </template>
    </el-main>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑轨迹" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form :model="editForm" label-width="100px" class="dialog-form">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" placeholder="请输入轨迹名称" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息"
          />
        </el-form-item>

        <!-- <el-divider content-position="left">更改坐标系</el-divider> -->

        <el-form-item label="原坐标系">
          <el-radio-group v-model="editForm.original_crs">
            <el-radio value="wgs84">WGS84</el-radio>
            <el-radio value="gcj02">GCJ02</el-radio>
            <el-radio value="bd09">BD09</el-radio>
          </el-radio-group>
          <div class="form-hint">更改坐标系会重新计算所有坐标并保存</div>
        </el-form-item>
      
      <!-- <el-divider content-position="left"></el-divider> -->
        <el-form-item label="地理信息">
          <el-button
                type="primary"
                :loading="fillingGeocoding"
                @click="handleFillGeocoding"
                class="fill-geo-btn"
              >
                <el-icon><LocationFilled /></el-icon>
                {{ fillingGeocoding ? '填充中...' : (track?.has_area_info || track?.has_road_info) ? '重新填充' : '填充' }}
          </el-button>
          <el-button
            @click="handleOpenGeoEditor"
            class="fill-geo-btn"
          >
            <el-icon><Edit /></el-icon>
            编辑
          </el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer-content">
          
          <div class="dialog-footer-right">
            <el-button @click="editDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="saving || changingCrs" @click="saveEdit">
              {{ changingCrs ? '更改中...' : '保存' }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 导出数据对话框 -->
    <el-dialog v-model="exportPointsDialogVisible" title="导出轨迹" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form label-width="100px" class="dialog-form">
        <el-form-item label="文件格式">
          <el-radio-group v-model="exportFormat">
            <el-radio value="gpx">GPX</el-radio>
            <el-radio value="kml">KML</el-radio>
            <el-radio value="csv">CSV</el-radio>
            <el-radio value="xlsx">XLSX</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="坐标系" v-if="exportFormat === 'gpx' || exportFormat === 'kml'">
          <el-radio-group v-model="exportCRS">
            <el-radio value="original">原始 ({{ track?.original_crs?.toUpperCase() }})</el-radio>
            <el-radio value="wgs84">WGS84</el-radio>
            <el-radio value="gcj02">GCJ02</el-radio>
            <el-radio value="bd09">BD09</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-alert type="info" :closable="false" style="margin-top: 10px">
          <template v-if="exportFormat === 'gpx'">
            导出为 GPX 格式，可导入到各种 GPS 设备和软件。包含时间、坐标、海拔等信息。
          </template>
          <template v-else-if="exportFormat === 'kml'">
            导出为 KML 格式，可导入到 Google Earth、两步路等应用。包含时间、坐标、海拔等信息。
          </template>
          <template v-else-if="exportFormat === 'csv'">
            导出为 UTF-8 带 BOM 的 CSV 格式，可使用 Excel 等电子表格软件打开。可以编辑地理信息，然后重新导入。
          </template>
          <template v-else>
            导出后可以编辑地理信息，然后重新导入。
          </template>
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
    <LiveRecordingDialog
      v-model:visible="recordingDetailVisible"
      :recording-id="currentRecordingId || 0"
      :token="currentRecordingToken || ''"
      :name="currentRecordingName || ''"
      :status="currentRecordingStatus || 'ended'"
      :fill-geocoding="currentRecordingFillGeocoding || false"
      :last-upload-at="currentRecordingLastUploadAt"
      :last-point-time="currentRecordingLastPointTime"
      :last-point-created-at="currentRecordingLastPointCreatedAt"
      @ended="handleRecordingEnded"
      @fill-geocoding-changed="handleFillGeocodingChanged"
      @refresh="refreshRecordingStatus"
    />

    <!-- 海报导出对话框 -->
    <PosterExportDialog
      v-model:visible="posterDialogVisible"
      :track="track"
      :points="points"
      :regions="regionTree"
      :map-ref="mapRef"
    />

    <ShareDialog
      v-model:visible="shareDialogVisible"
      :track-id="trackId"
      :initial-status="shareStatus"
      @update:status="shareStatus = $event"
    />

    <!-- 覆盖层导出对话框 -->
    <el-dialog
      v-model="overlayExportDialogVisible"
      title="导出覆盖层"
      :width="isMobile ? '95%' : '500px'"
    >
      <el-form :model="overlayExportConfig" label-width="100px">
        <el-form-item label="使用模板">
          <el-select v-model="selectedOverlayTemplate" placeholder="选择模板" style="width: 100%">
            <el-option
              v-for="tpl in overlayTemplates"
              :key="tpl.id"
              :label="tpl.name"
              :value="tpl.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="输出分辨率">
          <el-radio-group v-model="overlayExportConfig.resolution">
            <el-radio-button value="1920x1080">1080p</el-radio-button>
            <el-radio-button value="2560x1440">2K</el-radio-button>
            <el-radio-button value="3840x2160">4K</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="采样率">
          <el-radio-group v-model="overlayExportConfig.frameRate">
            <el-radio-button :value="1">1 fps（每秒1帧）</el-radio-button>
            <el-radio-button :value="2">2 fps</el-radio-button>
            <el-radio-button :value="5">5 fps</el-radio-button>
            <el-radio-button :value="0">全部</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="时间范围">
          <div class="range-inputs">
            <el-input-number
              v-model="overlayExportConfig.startIndex"
              :min="0"
              :max="points.length - 1"
              placeholder="起始索引"
            />
            <span>至</span>
            <el-input-number
              v-model="overlayExportConfig.endIndex"
              :min="-1"
              :max="points.length - 1"
              placeholder="-1 表示到最后"
            />
          </div>
          <el-button text @click="setFullRange">全部</el-button>
        </el-form-item>

        <el-form-item label="输出格式">
          <el-radio-group v-model="overlayExportConfig.outputFormat">
            <el-radio-button value="zip">ZIP 压缩包</el-radio-button>
            <el-radio-button value="png_sequence">PNG 序列</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-alert type="info" :closable="false">
          <template #title>
            预计生成 ~{{ estimatedFrames }} 帧
          </template>
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="overlayExportDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="exportOverlay" :loading="isExportingOverlay">
          开始导出
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, onBeforeUnmount, nextTick, watch, h } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'
import {
  ArrowLeft,
  HomeFilled,
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
  Loading,
  Link,
  Picture,
  Share,
  Film,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { trackApi, type Track, type TrackPoint, type FillProgressResponse, type RegionNode, type ShareStatus } from '@/api/track'
import { liveRecordingApi } from '@/api/liveRecording'
import { overlayTemplateApi } from '@/api/overlayTemplate'
import UniversalMap from '@/components/map/UniversalMap.vue'
import TrackAnimationPlayer from '@/components/animation/TrackAnimationPlayer.vue'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'
import { useAnimationStore } from '@/stores/animation'
import type { AnimationConfig } from '@/types/animation'
import { calculateDuration } from '@/utils/animationUtils'
import { roadSignApi } from '@/api/roadSign'
import { parseRoadNumber, type ParsedRoadNumber } from '@/utils/roadSignParser'
import { LiveTrackWebSocket, getCurrentToken, type PointAddedData } from '@/utils/liveTrackWebSocket'
import { getWebSocketOrigin } from '@/utils/origin'
import LiveRecordingDialog from '@/components/LiveRecordingDialog.vue'
import PosterExportDialog from '@/components/PosterExportDialog.vue'
import ShareDialog from '@/components/ShareDialog.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const configStore = useConfigStore()
const animationStore = useAnimationStore()

// 地图提供商（使用 ref 以便响应实际地图变化）
const mapProvider = ref(configStore.getEffectiveProvider())

// 处理地图提供商变化
function handleMapProviderChanged(provider: string) {
  console.log('[TrackDetail] Map provider changed:', provider)
  mapProvider.value = provider
}

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
const loadFailed = ref(false)  // 标记是否加载失败

// 标记组件是否已挂载，用于避免卸载后更新状态
const isMounted = ref(true)

const containerRef = ref<HTMLElement>()
const mapRef = ref()
const mapWrapperRef = ref<HTMLElement>()
const mapElementRef = ref<HTMLElement | null>(null)
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null  // 保存图表实例
let mapResizeObserver: ResizeObserver | null = null  // 地图容器大小监听器

// 编辑相关
const editDialogVisible = ref(false)
const saving = ref(false)
const changingCrs = ref(false)
const editForm = ref({
  name: '',
  description: '',
  original_crs: 'wgs84'
})

// 填充地理信息相关
const fillingGeocoding = ref(false)
const fillProgress = ref<{
  current: number
  total: number
  failed: number
  status: 'idle' | 'filling' | 'completed' | 'error' | 'stopped'
}>({ current: 0, total: 0, failed: 0, status: 'idle' })
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

// 实时记录详情相关（使用 LiveRecordingDialog 组件）
const recordingDetailVisible = ref(false)
const currentRecordingId = ref<number | null>(null)
const currentRecordingToken = ref<string | null>(null)
const currentRecordingName = ref<string | null>(null)
const currentRecordingStatus = ref<'active' | 'ended' | null>(null)
const currentRecordingFillGeocoding = ref<boolean>(false)
const currentRecordingLastUploadAt = ref<string | null>(null)
const currentRecordingLastPointTime = ref<string | null>(null)
const currentRecordingLastPointCreatedAt = ref<string | null>(null)

// 路径段高亮相关
const highlightedSegment = ref<{ start: number; end: number; nodeName: string } | null>(null)

// 实时轨迹最新点索引（用于显示绿色标记）
const latestPointIndex = computed(() => {
  // 只有活跃的实时记录时才显示最新点标记
  if (!track.value?.is_live_recording || track.value?.live_recording_status !== 'active' || !points.value.length) {
    return null
  }

  // 过滤出有有效坐标的点（与 trackWithPoints 逻辑一致）
  const validPoints = points.value.filter(p =>
    p.latitude_wgs84 != null &&
    p.longitude_wgs84 != null &&
    !isNaN(p.latitude_wgs84) &&
    !isNaN(p.longitude_wgs84)
  )

  if (validPoints.length === 0) return null

  // 找到 GPS 时间最新的点在 validPoints 中的索引
  let latestIndex = -1
  let latestTime: string | null = null

  validPoints.forEach((point, index) => {
    if (point.time && point.time > (latestTime || '')) {
      latestTime = point.time
      latestIndex = index
    }
  })

  return latestIndex >= 0 ? latestIndex : null
})

// 导出相关
const exportPointsDialogVisible = ref(false)
const exportFormat = ref<'gpx' | 'kml' | 'csv' | 'xlsx'>('gpx')
const exportCRS = ref('original')
const exporting = ref(false)

// 导入相关
const importDialogVisible = ref(false)
const importing = ref(false)

// 海报导出相关
const posterDialogVisible = ref(false)

// 覆盖层导出相关
const overlayExportDialogVisible = ref(false)
const overlayTemplates = ref<any[]>([])
const selectedOverlayTemplate = ref<number | null>(null)
const overlayExportConfig = ref({
  resolution: '1920x1080',
  frameRate: 1,
  startIndex: 0,
  endIndex: -1,
  outputFormat: 'zip'
})
const isExportingOverlay = ref(false)

// 覆盖层导出计算属性
const estimatedFrames = computed(() => {
  const total = overlayExportConfig.value.endIndex === -1
    ? points.value.length
    : overlayExportConfig.value.endIndex - overlayExportConfig.value.startIndex + 1
  const rate = overlayExportConfig.value.frameRate || 1
  return Math.ceil(total / rate)
})

// 加载覆盖层模板列表
const loadOverlayTemplates = async () => {
  try {
    const response = await overlayTemplateApi.list({ include_system: true })
    overlayTemplates.value = response.items
  } catch (error: any) {
    console.error('加载模板列表失败:', error)
  }
}

// 设置全范围
const setFullRange = () => {
  overlayExportConfig.value.startIndex = 0
  overlayExportConfig.value.endIndex = -1
}

// 导出覆盖层
const exportOverlay = async () => {
  if (!selectedOverlayTemplate.value) {
    ElMessage.warning('请选择模板')
    return
  }

  isExportingOverlay.value = true
  try {
    const blob = await overlayTemplateApi.exportOverlay(
      trackId.value,
      {
        template_id: selectedOverlayTemplate.value,
        resolution: overlayExportConfig.value.resolution,
        frame_rate: overlayExportConfig.value.frameRate,
        start_index: overlayExportConfig.value.startIndex,
        end_index: overlayExportConfig.value.endIndex,
        output_format: overlayExportConfig.value.outputFormat as 'zip' | 'png_sequence'
      }
    )

    // 下载文件
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `overlay_${trackId.value}.${overlayExportConfig.value.outputFormat === 'zip' ? 'zip' : 'png'}`
    a.click()
    URL.revokeObjectURL(url)

    ElMessage.success('导出成功')
    overlayExportDialogVisible.value = false
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '导出失败')
  } finally {
    isExportingOverlay.value = false
  }
}

// 分享相关
const shareDialogVisible = ref(false)
const shareStatus = ref<ShareStatus | null>(null)

const importFile = ref<File | null>(null)
const importMatchMode = ref<'index' | 'time'>('index')
const importTimezone = ref<string>('UTC+8')
const importTimeTolerance = ref<number>(1.0)
const uploadRef = ref<UploadInstance>()

// 实时更新相关
let liveTrackWs: LiveTrackWebSocket | null = null
const isLiveUpdating = ref(false)
const liveUpdateStatus = ref<'connected' | 'disconnected' | 'error'>('disconnected')
// 区域更新节流：最多每 10 秒更新一次
let regionUpdateTimer: number | null = null
const REGION_UPDATE_INTERVAL = 10000 // 10 秒

// 判断是否是"待记录"状态（活跃的实时记录且没有点）
const isWaitingForPoints = computed(() => {
  return track.value?.is_live_recording && track.value?.live_recording_status === 'active' && points.value.length === 0
})

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

// 动画配置
const animationConfig = computed<AnimationConfig | null>(() => {
  if (!track.value || !points.value.length || points.value.length < 2) return null

  return {
    trackId: track.value.id,
    trackPoints: points.value,
    startTime: points.value[0].time || '',
    endTime: points.value[points.value.length - 1].time || '',
    duration: calculateDuration(points.value),
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
  } else if (command === 'exportPoints') {
    exportPointsDialogVisible.value = true
  } else if (command === 'import') {
    importDialogVisible.value = true
  } else if (command === 'poster') {
    posterDialogVisible.value = true
  } else if (command === 'overlayExport') {
    overlayExportDialogVisible.value = true
  } else if (command === 'share') {
    shareDialogVisible.value = true
  }
}

// 获取轨迹详情
async function fetchTrackDetail() {
  try {
    // 如果是虚拟 ID（负数），说明是等待上传点的实时记录
    if (trackId.value < 0) {
      const recordingId = -trackId.value
      const result = await liveRecordingApi.getDetail(recordingId)
      if (!isMounted.value) return
      track.value = result
      points.value = []  // 空轨迹没有点

      // 如果后端返回了真实轨迹 ID，说明已经有轨迹点了
      if (track.value.id > 0) {
        console.log(`[TrackDetail] 虚拟轨迹已转为真实轨迹: ${track.value.id}`)
        // 更新 trackId，这样后续的 fetchTrackPoints 等函数能正确工作
        trackId.value = track.value.id
        // 重定向到正确的 URL（不影响当前组件的数据）
        router.replace(`/tracks/${track.value.id}`)
        // 重新获取轨迹点数据
        await fetchTrackPoints()
        return
      }
    } else {
      const result = await trackApi.getDetail(trackId.value)
      if (!isMounted.value) return
      track.value = result
    }
  } catch (error) {
    // 错误已在拦截器中处理
    if (isMounted.value) {
      loadFailed.value = true
    }
  }
}

// 获取轨迹点
async function fetchTrackPoints() {
  // 如果是虚拟 ID（负数），跳过（空轨迹没有点）
  if (trackId.value < 0) {
    points.value = []
    return
  }

  try {
    const response = await trackApi.getPoints(trackId.value)
    if (isMounted.value) {
      points.value = response.points
    }
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
    if (!isMounted.value) return
    regionTree.value = response.regions
    regionStats.value = response.stats
  } catch (error) {
    // 错误已在拦截器中处理
    if (isMounted.value) {
      regionTree.value = []
      regionStats.value = { province: 0, city: 0, district: 0, road: 0 }
    }
  } finally {
    if (isMounted.value) {
      regionTreeLoading.value = false
    }
  }
}

// 格式化节点显示名称
function formatNodeLabel(node: RegionNode): string {
  // 如果有提升显示的名称（子节点的名称），优先使用
  if (node.promoted_name) {
    // 对于提升显示的道路节点，使用道路编号格式
    if (node.promoted_type === 'road' && node.road_number) {
      const roadNumbers = node.road_number.split(',').map(s => s.trim()).join(' / ')
      if (node.promoted_name && node.promoted_name !== '（无名）') {
        return `${roadNumbers} ${node.promoted_name}`
      }
      return roadNumbers
    }
    return node.promoted_name
  }

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
    // 回放期间禁用图表-地图联动
    if (animationStore.isPlaying) return

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
    // 回放期间禁用图表-地图联动
    if (animationStore.isPlaying) return

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

// 处理动画位置变化
function handleAnimationPositionChange(position: { lat: number; lng: number; bearing: number; speed: number | null; elevation: number | null; time: string | null }) {
  // 可以在这里添加自定义逻辑，比如同步到图表等
}

// 处理动画区段更新
function handleAnimationSegmentUpdate(passedEnd: number) {
  highlightedPointIndex.value = passedEnd
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

// 打开地理信息在线编辑器
function handleOpenGeoEditor() {
  // 关闭编辑对话框
  editDialogVisible.value = false
  // 导航到地理编辑器页面
  router.push(`/tracks/${trackId.value}/geo-editor`)
}

async function handleInterpolationApplied() {
  // 重新加载轨迹数据
  await fetchTrackDetail()
  await fetchTrackPoints()
}

// 处理编辑命令（下拉菜单）
function handleEditCommand(command: string) {
  switch (command) {
    case 'geo-editor':
      router.push(`/tracks/${trackId.value}/geo-editor`)
      break
    case 'interpolation':
      router.push(`/tracks/${trackId.value}/interpolation`)
      break
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
        const { current, failed } = response.progress
        const total = current + failed
        // 根据失败数量显示不同的提示
        if (current > 0 && failed === 0) {
          // 全部成功
          ElMessage.success('地理信息填充完成')
        } else if (current > 0 && failed > 0) {
          // 部分失败
          const failedPercent = Math.round((failed / total) * 100)
          ElMessage.warning(`地理信息填充完成，但包含 ${failed} 条失败数据（占 ${failedPercent}%），请自行填充失败部分`)
        } else if (current === 0 && failed > 0) {
          // 全部失败
          ElMessage.error('地理信息填充失败，请自行填充')
        }
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
  // 跳过虚拟轨迹（等待上传点的实时记录）
  if (!trackId.value || trackId.value < 0) {
    return
  }

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

// 显示实时记录详情对话框
async function showRecordingDetail() {
  if (!track.value?.live_recording_id || !track.value?.live_recording_token) return

  try {
    // 从后端获取最新的实时记录数据（包含 fill_geocoding 和最新上传时间）
    const recording = await liveRecordingApi.getList('active')
    const currentRecording = recording.find(r => r.id === track.value?.live_recording_id)

    if (!currentRecording) {
      ElMessage.error('找不到实时记录')
      return
    }

    currentRecordingId.value = track.value.live_recording_id
    currentRecordingToken.value = track.value.live_recording_token
    currentRecordingName.value = track.value.name
    currentRecordingStatus.value = track.value.live_recording_status
    currentRecordingFillGeocoding.value = currentRecording.fill_geocoding || track.value.fill_geocoding || false
    currentRecordingLastUploadAt.value = currentRecording.last_upload_at || null
    currentRecordingLastPointTime.value = currentRecording.last_point_time || null
    currentRecordingLastPointCreatedAt.value = track.value.last_point_created_at || null
    recordingDetailVisible.value = true
  } catch (error) {
    ElMessage.error('获取实时记录信息失败')
  }
}

// 更新填充地理信息设置
async function updateRecordingFillGeocoding(value: boolean) {
  if (!currentRecordingId.value) return

  const originalValue = currentRecordingFillGeocoding.value

  try {
    await liveRecordingApi.updateFillGeocoding(currentRecordingId.value, value)
    // 成功后更新本地状态
    currentRecordingFillGeocoding.value = value
    // 同时更新 track 的 fill_geocoding 值（如果存在）
    if (track.value) {
      track.value.fill_geocoding = value
    }
    ElMessage.success(value ? '已开启自动填充地理信息' : '已关闭自动填充地理信息')
  } catch (error) {
    // 失败时恢复到原来的值
    currentRecordingFillGeocoding.value = originalValue
    console.error('更新填充地理信息设置失败:', error)
  }
}

// 处理填充地理信息变更（由 LiveRecordingDialog 触发）
function handleFillGeocodingChanged(value: boolean) {
  currentRecordingFillGeocoding.value = value
  // 同时更新 track 的 fill_geocoding 值
  if (track.value) {
    track.value.fill_geocoding = value
  }
}

// 刷新实时记录状态
async function refreshRecordingStatus() {
  if (!currentRecordingId.value) return

  try {
    const status = await liveRecordingApi.getStatus(currentRecordingId.value)
    // 更新状态
    currentRecordingLastUploadAt.value = status.last_upload_at
    currentRecordingLastPointTime.value = status.last_point_time
    currentRecordingLastPointCreatedAt.value = status.last_point_created_at

    // 同时更新 track 的数据
    if (track.value) {
      track.value.last_upload_at = status.last_upload_at
      track.value.last_point_time = status.last_point_time
      track.value.last_point_created_at = status.last_point_created_at
    }
  } catch (error) {
    // 静默处理错误
  }
}

// 处理记录结束事件
function handleRecordingEnded() {
  recordingDetailVisible.value = false
  // 重新加载轨迹数据
  fetchTrackDetail()
}

// 显示编辑对话框
function showEditDialog() {
  if (track.value) {
    editForm.value.name = track.value.name
    editForm.value.description = track.value.description || ''
    editForm.value.original_crs = track.value.original_crs || 'wgs84'
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
    // 检查是否需要更改坐标系
    const needsCrsChange = editForm.value.original_crs !== track.value.original_crs

    if (needsCrsChange) {
      // 需要更改坐标系
      try {
        await ElMessageBox.confirm(
          '更改坐标系会重新计算所有坐标并保存，此操作不可撤销。如果此前填充了轨迹，可能需要重新填充。是否继续？',
          '确认更改坐标系',
          {
            confirmButtonText: '继续',
            cancelButtonText: '取消',
            type: 'warning',
          }
        )
      } catch {
        // 用户取消
        saving.value = false
        return
      }

      changingCrs.value = true
      const updated = await trackApi.changeCrs(track.value.id, editForm.value.original_crs)
      track.value = updated
      // 重新加载轨迹点数据
      await fetchTrackPoints()
      // 强制刷新地图
      await nextTick()
      if (mapRef.value?.resize) {
        mapRef.value.resize()
      }
      if (mapRef.value?.fitBounds) {
        mapRef.value.fitBounds()
      }
      ElMessage.success('坐标系更改成功')
    } else {
      // 只更新名称和描述
      const updated = await trackApi.update(track.value.id, {
        name: editForm.value.name.trim(),
        description: editForm.value.description.trim() || undefined
      })
      track.value = updated
      ElMessage.success('保存成功')
    }

    editDialogVisible.value = false
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
    changingCrs.value = false
  }
}

// 导出轨迹
async function exportPoints() {
  try {
    exporting.value = true
    let url: string
    let defaultFilename: string

    if (exportFormat.value === 'gpx') {
      // GPX 使用 download API
      url = trackApi.download(trackId.value, exportCRS.value)
      defaultFilename = `track_${trackId.value}.gpx`
    } else if (exportFormat.value === 'kml') {
      // KML 需要 crs 参数
      url = trackApi.exportPoints(trackId.value, exportFormat.value, exportCRS.value)
      defaultFilename = `track_${trackId.value}.kml`
    } else {
      // CSV 和 XLSX
      url = trackApi.exportPoints(trackId.value, exportFormat.value)
      defaultFilename = `track_${trackId.value}_points.${exportFormat.value}`
    }

    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (!response.ok) {
      throw new Error('导出失败')
    }

    // 获取文件名（优先使用 filename* RFC 5987）
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = defaultFilename
    if (contentDisposition) {
      // 优先匹配 filename*=UTF-8''encoded-filename
      const starMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
      if (starMatch) {
        // 解码 URL 编码的文件名
        filename = decodeURIComponent(starMatch[1])
      } else {
        // 回退到 filename 参数（URL 编码）
        const match = contentDisposition.match(/filename="([^"]+)"/)
        if (match) filename = decodeURIComponent(match[1])
      }
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
  if (hours > 0) return `${hours}h ${minutes}min`
  return `${minutes}min`
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

// ========== 实时更新相关 ==========

/**
 * 启动实时更新（如果是实时轨迹）
 */
function startLiveUpdate() {
  if (!track.value?.is_live_recording || !track.value.live_recording_token) {
    return
  }

  if (track.value.live_recording_status !== 'active') {
    console.log('[LiveUpdate] 记录已结束，不启动实时更新')
    return
  }

  const token = track.value.live_recording_token
  const recordingId = track.value.live_recording_id

  if (!recordingId) {
    console.warn('[LiveUpdate] 缺少 recording_id')
    return
  }

  // 打印调试信息
  const wsOrigin = getWebSocketOrigin()
  console.log(`[LiveUpdate] ========== 启动实时更新 ==========`)
  console.log(`[LiveUpdate] recording_id=${recordingId}`)
  console.log(`[LiveUpdate] token=${token.substring(0, 16)}...`)
  console.log(`[LiveUpdate] getWebSocketOrigin() 返回: ${wsOrigin}`)
  console.log(`[LiveUpdate] 预期 WebSocket URL: ${wsOrigin}/api/ws/live-recording/${recordingId}?token=${token}`)
  console.log(`[LiveUpdate] VITE_ORIGIN=${import.meta.env.VITE_ORIGIN || '(未设置)'}`)
  console.log(`[LiveUpdate] VITE_DEBUG_WS=${import.meta.env.VITE_DEBUG_WS || '(未设置，默认开启)'}`)
  console.log(`[LiveUpdate] ======================================`)

  try {
    liveTrackWs = new LiveTrackWebSocket(token, recordingId)
    isLiveUpdating.value = true

    // 设置重连判断回调：只有记录状态为 active 时才重连
    liveTrackWs.setShouldReconnectCallback(() => {
      const shouldReconnect = track.value?.live_recording_status === 'active'
      console.log('[LiveUpdate] 重连判断:', shouldReconnect ? '继续重连' : '停止重连（记录已结束）')
      return shouldReconnect
    })

    // 监听连接状态
    liveTrackWs.on('connected', () => {
      console.log('[LiveUpdate] WebSocket 已连接')
      liveUpdateStatus.value = 'connected'
    })

    // 监听断开连接
    liveTrackWs.on('disconnected', async (message) => {
      console.log('[LiveUpdate] WebSocket 已断开:', message.data)
      liveUpdateStatus.value = 'disconnected'

      // 主动获取最新记录状态（因为可能是记录被结束导致断开）
      if (track.value?.is_live_recording && track.value?.live_recording_id) {
        try {
          const status = await liveRecordingApi.getStatus(track.value.live_recording_id)
          console.log('[LiveUpdate] 获取到最新记录状态:', status.status)

          // 更新 track 状态
          if (track.value) {
            track.value.live_recording_status = status.status
          }

          // 如果记录已结束，停止实时更新
          if (status.status !== 'active') {
            console.log('[LiveUpdate] 记录已结束，停止实时更新')
            stopLiveUpdate()
            // 刷新页面数据以显示最终状态
            fetchTrackDetail()
          }
        } catch (error) {
          console.error('[LiveUpdate] 获取记录状态失败:', error)
        }
      }
    })

    // 监听新点添加
    liveTrackWs.on('point_added', (message) => {
      console.log('[LiveUpdate] 收到新点:', message)
      handleNewPointAdded(message.data as PointAddedData)
    })

    // 连接
    liveTrackWs.connect()
  } catch (error) {
    console.error('[LiveUpdate] 启动失败:', error)
    liveUpdateStatus.value = 'error'
  }
}

/**
 * 停止实时更新
 */
function stopLiveUpdate() {
  console.log('[LiveUpdate] 停止实时更新')
  if (liveTrackWs) {
    liveTrackWs.disconnect()
    liveTrackWs = null
  }
  isLiveUpdating.value = false
  liveUpdateStatus.value = 'disconnected'

  // 清除区域更新定时器
  if (regionUpdateTimer) {
    clearTimeout(regionUpdateTimer)
    regionUpdateTimer = null
  }

  // 停止时立即获取一次完整的区域数据
  fetchRegions()
}

/**
 * 延迟更新经过区域（使用节流）
 */
function scheduleRegionUpdate() {
  // 清除之前的定时器
  if (regionUpdateTimer) {
    clearTimeout(regionUpdateTimer)
  }

  // 设置新的定时器，10 秒后执行
  regionUpdateTimer = window.setTimeout(() => {
    console.log('[LiveUpdate] 更新经过区域')
    fetchRegions()
    regionUpdateTimer = null
  }, REGION_UPDATE_INTERVAL)
}

/**
 * 处理新点添加事件
 */
async function handleNewPointAdded(data: PointAddedData) {
  const { point, stats } = data

  // 添加新点到 points 数组
  points.value.push({
    id: point.id,
    point_index: point.point_index,
    time: point.time,
    created_at: point.created_at || null,
    latitude: point.latitude_wgs84 || point.latitude,
    longitude: point.longitude_wgs84 || point.longitude,
    latitude_wgs84: point.latitude_wgs84 ?? point.latitude ?? null,
    longitude_wgs84: point.longitude_wgs84 ?? point.longitude ?? null,
    latitude_gcj02: point.latitude_gcj02 ?? null,
    longitude_gcj02: point.longitude_gcj02 ?? null,
    latitude_bd09: point.latitude_bd09 ?? null,
    longitude_bd09: point.longitude_bd09 ?? null,
    elevation: point.elevation,
    speed: point.speed,
    bearing: null,
    province: point.province || null,
    city: point.city || null,
    district: point.district || null,
    road_name: point.road_name || null,
    road_number: point.road_number || null,
    province_en: point.province_en || null,
    city_en: point.city_en || null,
    district_en: point.district_en || null,
    road_name_en: point.road_name_en || null,
    memo: point.memo || null,
  })

  // 按时间戳排序（防止乱序）
  points.value.sort((a, b) => {
    const timeA = a.time ? new Date(a.time).getTime() : 0
    const timeB = b.time ? new Date(b.time).getTime() : 0
    return timeA - timeB
  })

  // 更新轨迹统计（包括结束时间）
  if (track.value) {
    track.value.distance = stats.distance
    track.value.duration = stats.duration
    track.value.elevation_gain = stats.elevation_gain
    track.value.elevation_loss = stats.elevation_loss
    // 只有当新点时间更晚时才更新结束时间（避免乱序点导致倒流）
    if (point.time && (!track.value.end_time || point.time > track.value.end_time)) {
      track.value.end_time = point.time
    }
    // 更新最后轨迹点时间（用于记录配置对话框显示 GPS 时间）
    track.value.last_point_time = point.time
    // 更新最后轨迹点服务器接收时间（用于地图显示）
    track.value.last_point_created_at = point.created_at || point.time
    // 如果开始时间为空（第一个点），设置为当前点的时间
    if (!track.value.start_time && point.time) {
      track.value.start_time = point.time
    } else if (point.time && (!track.value.start_time || point.time < track.value.start_time)) {
      // 同样处理开始时间：只有当新点时间更早时才更新
      track.value.start_time = point.time
    }
  }

  // 延迟更新经过区域（节流：最多每 10 秒更新一次）
  scheduleRegionUpdate()

  // 重新渲染图表
  nextTick(() => {
    renderChart()
  })

  // 如果地图已初始化，触发地图更新
  if (mapRef.value?.refresh) {
    mapRef.value.refresh()
  }
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

  // 启动实时更新（如果是实时轨迹）
  if (track.value?.is_live_recording && track.value.live_recording_status === 'active') {
    startLiveUpdate()
  }

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

// 组件即将卸载时设置标志
onBeforeUnmount(() => {
  isMounted.value = false
})

// 监听布局切换，重新渲染图表
watch(isTallScreen, () => {
  nextTick(() => {
    renderChart()
  })
})

// 监听覆盖层导出对话框打开
watch(overlayExportDialogVisible, (newVal) => {
  if (newVal && overlayTemplates.value.length === 0) {
    loadOverlayTemplates()
  }
})

onUnmounted(() => {
  stopPollingProgress()

  // 停止实时更新
  stopLiveUpdate()

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
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
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

/* 实时更新状态指示器 */
.live-status-indicator {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  cursor: pointer;
}

/* 实时记录中：红色闪动 */
.live-status-indicator.status-recording {
  background-color: #f56c6c;
  animation: pulse-red 1.5s ease-in-out infinite;
}

/* 连接断开/错误：黄色 */
.live-status-indicator.status-error {
  background-color: #e6a23c;
}

@keyframes pulse-red {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
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

/* 等待记录中样式 */
.waiting-for-points {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  gap: 12px;
  text-align: center;
}

.waiting-icon {
  font-size: 48px;
  color: #409eff;
  animation: pulse 2s ease-in-out infinite;
}

.waiting-text {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin: 0;
}

.waiting-hint {
  font-size: 14px;
  color: #999;
  margin: 0;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
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
  overflow-x: auto;
}

/* 让 el-tree 的宽度由内容决定，而不是填充父容器 */
.region-tree-container :deep(.el-tree) {
  display: inline-block;
  min-width: 100%;
}

.region-tree-container :deep(.el-tree-node__content) {
  min-width: max-content;
}

.region-tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  width: 100%;
  min-width: max-content;
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

.fill-failed-count {
  color: #f56c6c;
  font-weight: 500;
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

  .map-content {
    width: 100%;
    height: 100%;
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

.map-content {
  width: 100%;
  height: 100%;
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

/* 骨架屏样式 */
.detail-skeleton {
  width: 100%;
}

.card-skeleton-wrapper {
  padding: 20px;
}

.map-skeleton-content {
  padding: 20px;
  min-height: 400px;
}

.chart-skeleton-content {
  padding: 20px;
  min-height: 180px;
}

/* 表单提示文本 */
.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.5;
  padding-left: 24px;
}

/* 编辑对话框底部 */
.dialog-footer-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
}

.dialog-footer-right {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.fill-geo-btn {
  flex-shrink: 0;
}

:deep(.el-dialog__footer) {
  padding: 12px 20px;
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

/* 覆盖层导出对话框样式 */
.range-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
