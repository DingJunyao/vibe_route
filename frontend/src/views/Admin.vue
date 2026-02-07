<template>
  <div class="admin-container">
    <el-container>
      <el-header>
        <div class="header-content">
          <el-button @click="$router.back()" :icon="ArrowLeft" class="nav-btn" />
          <el-button @click="$router.push('/home')" :icon="HomeFilled" class="nav-btn home-nav-btn" />
          <h1>后台管理</h1>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-icon>
                <UserIcon />
              </el-icon>
              <span class="username">{{ authStore.user?.username }}</span>
              <el-icon class="el-icon--right">
                <ArrowDown />
              </el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="tracks">
                  <el-icon>
                    <List />
                  </el-icon>
                  轨迹列表
                </el-dropdown-item>
                <el-dropdown-item command="logout">
                  <el-icon>
                    <SwitchButton />
                  </el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <el-tabs v-model="activeTab" type="border-card">
          <!-- 系统配置 -->
          <el-tab-pane label="系统配置" name="config">
            <div class="config-tab-content">
              <!-- 加载中显示骨架屏 -->
              <div v-if="loadingConfig" class="config-skeleton">
                <el-skeleton :rows="10" animated />
              </div>
              <!-- 加载完成后显示内容 -->
              <el-card v-else shadow="never">
                <el-form :model="config" label-width="150px" class="config-form">
                  <!-- 注册设置 -->
                  <div class="form-section">
                    <div class="section-title">注册设置</div>
                    <el-form-item label="允许注册">
                      <el-switch v-model="config.registration_enabled" />
                      <span class="form-tip">是否开放用户注册</span>
                    </el-form-item>
                    <el-form-item label="需要邀请码">
                      <el-switch v-model="config.invite_code_required" />
                      <span class="form-tip">注册时是否需要邀请码</span>
                    </el-form-item>
                  </div>

                  <!-- 显示设置 -->
                  <div class="form-section">
                    <div class="section-title">显示设置</div>
                    <el-form-item label="道路编号显示标牌">
                      <el-switch v-model="config.show_road_sign_in_region_tree" />
                      <span class="form-tip">开启后，经过区域中的道路编号将显示为对应的道路标志 SVG</span>
                    </el-form-item>
                  </div>

                  <!-- 海报生成设置 -->
                  <div class="form-section">
                    <div class="section-title">海报生成设置</div>
                    <el-form-item label="允许服务器生成">
                      <el-switch v-model="config.allow_server_poster" />
                      <span class="form-tip">允许用户使用服务器生成海报。关闭后，用户只能使用浏览器生成，且无法在百度地图或移动设备上导出海报</span>
                    </el-form-item>
                  </div>

                  <!-- 地图设置 -->
                  <div class="form-section">
                    <div class="section-title">地图设置</div>
                    <div class="section-description">
                      <p>选择单选按钮设为默认地图，使用开关启用/禁用地图，<span class="desktop-only">拖拽</span><span class="mobile-only">点击左边的向上
                          /
                          向下按钮</span>调整显示顺序。</p>
                      <p>对于高德地图、百度地图、腾讯地图，如果不填 Key，仍然可以使用其点阵图层，但清晰度、更新速度不如矢量图层。</p>
                    </div>
                    <draggable v-model="allMapLayers" item-key="id" handle=".drag-handle" @end="onDragEnd"
                      class="map-layers-list">
                      <template #item="{ element: layer }">
                        <div class="map-layer-item" :class="{ 'is-default': layer.id === config.default_map_provider }">
                          <!-- 第一行：拖拽手柄、名称、开关、状态 -->
                          <div class="map-layer-main">
                            <el-icon class="drag-handle desktop-only">
                              <Rank />
                            </el-icon>
                            <!-- 移动端排序按钮 -->
                            <div class="mobile-sort-buttons">
                              <el-button type="primary" :icon="ArrowUp" size="small" text
                                :disabled="isFirstLayer(layer)" @click="moveLayerUp(layer)" />
                              <el-button type="primary" :icon="ArrowDown" size="small" text
                                :disabled="isLastLayer(layer)" @click="moveLayerDown(layer)" />
                            </div>
                            <div class="layer-info">
                              <el-radio :model-value="config.default_map_provider" :value="layer.id"
                                @change="config.default_map_provider = layer.id" :disabled="!layer.enabled">
                                <span class="layer-name">{{ layer.name }}</span>
                                <span class="layer-id">({{ layer.id }})</span>
                              </el-radio>
                            </div>
                            <el-switch v-model="layer.enabled" @change="onMapLayerToggle(layer)"
                              :disabled="layer.id === config.default_map_provider && layer.enabled" />
                            <span class="layer-status">
                              <template v-if="layer.id === config.default_map_provider">
                                <el-tag size="small" type="success">默认</el-tag>
                              </template>
                              <template v-else-if="layer.enabled">
                                <el-tag size="small" type="info">已启用</el-tag>
                              </template>
                              <template v-else>
                                <el-tag size="small" type="warning">已禁用</el-tag>
                              </template>
                            </span>
                          </div>
                          <!-- 第二行：API 配置输入框 -->
                          <div class="map-layer-config">
                            <!-- 天地图 tk 输入框 -->
                            <el-input v-if="layer.id === 'tianditu'" v-model="layer.tk" placeholder="启用了瓦片服务的浏览器端应用 tk"
                              clearable show-password class="config-input" />
                            <!-- 高德地图 JS API Key 和安全密钥输入框 -->
                            <template v-if="layer.id === 'amap'">
                              <el-input v-model="layer.api_key" placeholder="绑定服务为“Web 端”的 Key（矢量图必填）" clearable
                                show-password class="config-input" />
                              <el-input v-model="layer.security_js_code" placeholder="对应安全密钥（矢量图可选，如有必填）" clearable
                                show-password class="config-input" />
                            </template>
                            <!-- 腾讯地图 API Key 输入框 -->
                            <el-input v-if="layer.id === 'tencent'" v-model="layer.api_key" placeholder="Key（矢量图必填）"
                              clearable show-password class="config-input" />
                            <!-- 百度地图 API Key 输入框 -->
                            <el-input v-if="layer.id === 'baidu'" v-model="layer.api_key" placeholder="浏览器端应用 AK（矢量图必填）"
                              clearable show-password class="config-input" />
                          </div>
                        </div>
                      </template>
                    </draggable>
                  </div>

                  <!-- 地理编码设置 -->
                  <div class="form-section">
                    <div class="section-title">地理编码设置</div>
                    <el-form-item label="编码提供商">
                      <el-radio-group v-model="config.geocoding_provider" @change="onGeocodingProviderChange">
                        <el-radio value="gdf">GDF</el-radio>
                        <el-radio value="nominatim">Nominatim</el-radio>
                        <el-radio value="amap">高德地图</el-radio>
                        <el-radio value="baidu">百度地图</el-radio>
                      </el-radio-group>
                      <div class="radio-hint">
                        <template v-if="config.geocoding_provider === 'gdf'">
                          只能够读取行政区划，且只能精确到县级。使用“空间计算设置”中的配置。
                        </template>
                        <template v-else-if="config.geocoding_provider === 'nominatim'">
                          需自行部署，部署麻烦，占用空间大（中国大陆的数据下载解压处理后会占用 126 GB，初次部署要花费 20
                          小时）；但能够读取行政区划的英文（只有县级有行政级别名称）以及道路信息（不稳定，部分道路能读取英文）
                        </template>
                        <template v-else-if="config.geocoding_provider === 'amap'">
                          配额较多（个人开发者每月 150,000 次 API 调用），但个人版不支持英文
                        </template>
                        <template v-else-if="config.geocoding_provider === 'baidu'">
                          配额小（个人开发者每日 300 次 API 调用，每秒一次点位记录只能处理五分钟的）
                        </template>
                      </div>
                    </el-form-item>

                    <!-- Nominatim 配置 -->
                    <template v-if="config.geocoding_provider === 'nominatim'">
                      <el-form-item label="Nominatim URL">
                        <el-input v-model="config.geocoding_config.nominatim.url" placeholder="http://localhost:8080" />
                        <span class="form-hint">自建 Nominatim 服务的地址</span>
                      </el-form-item>
                    </template>

                    <!-- GDF 配置 -->
                    <template v-if="config.geocoding_provider === 'gdf'">
                      <el-form-item label="数据统计">
                        <el-button @click="showAdminDivisionStats" :loading="loadingDivisionStats">
                          查看行政区划数据
                        </el-button>
                        <span class="form-hint">检查数据库中的行政区划数据完整性</span>
                      </el-form-item>

                      <!-- DataV GeoJSON 行政区划导入 -->
                      <el-form-item label="数据导入">
                        <div class="datav-import-section">
                          <!-- 导入模式选择 -->
                          <el-radio-group v-model="datavImportMode" @change="onDatavImportModeChange" :disabled="datavImporting">
                            <el-radio value="full">全量更新</el-radio>
                            <el-radio value="bounds">仅更新边界</el-radio>
                            <el-radio value="provinces">按省份更新</el-radio>
                          </el-radio-group>
                          <div class="radio-hint">
                            <template v-if="datavImportMode === 'full'">
                              从 <el-link href="https://datav.aliyun.com/portal/school/atlas/area_selector" target="_blank" type="primary">阿里 DataV</el-link> 获取全国所有行政区划数据（省/市/区县），或者从 <el-link href="https://map.vanbyte.com/street.html" target="_blank" type="primary">全国行政区划边界 GeoJSON 数据</el-link> 获取压缩包上传。
                            </template>
                            <template v-else-if="datavImportMode === 'bounds'">
                              仅更新边界框数据，不修改行政区划基础信息
                            </template>
                            <template v-else>
                              选择需要更新的省份，仅获取指定省份的数据
                            </template>
                          </div>

                          <!-- 按省份选择 -->
                          <div v-if="datavImportMode === 'provinces'" class="province-selector">
                            <el-select
                              v-model="datavSelectedProvinces"
                              multiple
                              filterable
                              placeholder="请选择省份"
                              :loading="loadingProvinces"
                              :disabled="datavImporting"
                              style="width: 100%"
                            >
                              <el-option
                                v-for="prov in datavProvinceList"
                                :key="prov.code"
                                :label="prov.name"
                                :value="prov.code"
                              />
                            </el-select>
                          </div>

                          <!-- 强制覆盖选项 -->
                          <div class="force-option">
                            <el-checkbox v-model="datavForceOverwrite" :disabled="datavImporting">
                              强制覆盖已有数据
                            </el-checkbox>
                            <span class="form-hint-inline">覆盖现有的中心点和边界框数据</span>
                          </div>

                          <!-- 操作按钮 -->
                          <div class="import-actions">
                            <el-button
                              type="primary"
                              @click="importFromDataVOnline"
                              :loading="datavImporting"
                              :disabled="datavImportMode === 'provinces' && datavSelectedProvinces.length === 0"
                            >
                              在线更新
                            </el-button>
                            <el-upload
                              :show-file-list="false"
                              :auto-upload="false"
                              accept=".zip,.rar"
                              :on-change="handleDatavUploadChange"
                              :disabled="datavImporting"
                            >
                              <el-button :loading="datavImporting" :disabled="datavImporting">
                                上传压缩包
                              </el-button>
                            </el-upload>
                            <el-button
                              v-if="datavUploadFile"
                              type="success"
                              @click="importFromUpload"
                              :loading="datavImporting"
                            >
                              开始导入 ({{ datavUploadFile.name }})
                            </el-button>
                          </div>

                          <!-- 导入进度 -->
                          <div v-if="datavImporting && datavImportProgress" class="import-progress">
                            <el-progress
                              :percentage="datavImportProgress.progress"
                              :status="datavImportProgress.status === 'failed' ? 'exception' : undefined"
                            />
                            <div class="progress-text">
                              <span v-if="datavImportProgress.status === 'running'">正在导入...</span>
                              <span v-else-if="datavImportProgress.status === 'pending'">等待中...</span>
                              <span v-else-if="datavImportProgress.status === 'completed'">导入完成</span>
                              <span v-else-if="datavImportProgress.status === 'failed'" class="error-text">
                                {{ datavImportProgress.error || '导入失败' }}
                              </span>
                            </div>
                          </div>

                          <!-- 当前状态显示 -->
                          <div v-if="datavDivisionStatus" class="division-status">
                            <span class="status-label">当前数据：</span>
                            <span>{{ datavDivisionStatus.total }} 条记录</span>
                            <span class="status-sep">|</span>
                            <span>有边界 {{ datavDivisionStatus.has_bounds }}</span>
                            <span class="status-sep">|</span>
                            <span>有中心点 {{ datavDivisionStatus.has_center }}</span>
                          </div>
                        </div>
                      </el-form-item>
                    </template>

                    <!-- 高德地图配置 -->
                    <template v-if="config.geocoding_provider === 'amap'">
                      <el-form-item label="API Key">
                        <el-input v-model="config.geocoding_config.amap.api_key" placeholder="绑定服务为“Web 服务”的 Key"
                          show-password />
                      </el-form-item>
                      <el-form-item label="并发频率">
                        <el-input-number v-model="config.geocoding_config.amap.freq" :min="1" :max="50"
                          controls-position="right" />
                        <span class="form-hint">每秒请求数，建议值为 3</span>
                      </el-form-item>
                    </template>

                    <!-- 百度地图配置 -->
                    <template v-if="config.geocoding_provider === 'baidu'">
                      <el-form-item label="API Key">
                        <el-input v-model="config.geocoding_config.baidu.api_key" placeholder="服务端应用 AK"
                          show-password />
                      </el-form-item>
                      <el-form-item label="并发频率">
                        <el-input-number v-model="config.geocoding_config.baidu.freq" :min="1" :max="50"
                          controls-position="right" />
                        <span class="form-hint">每秒请求数，建议值为 3</span>
                      </el-form-item>
                      <el-form-item label="获取英文信息">
                        <el-switch v-model="config.geocoding_config.baidu.get_en_result" />
                        <span class="form-hint">开启后会额外请求英文版本的地理信息</span>
                      </el-form-item>
                    </template>
                  </div>

                  <!-- 空间计算设置（仅 PostgreSQL 显示） -->
                  <div v-if="databaseInfo && databaseInfo.database_type === 'postgresql'" class="form-section">
                    <div class="section-title">空间计算设置</div>
                    <!-- 未启用 PostGIS -->
                    <div v-if="!databaseInfo.postgis_enabled" class="postgis-notice">
                      <el-icon>
                        <InfoFilled />
                      </el-icon>
                      <span>启用 PostGIS 可以更高效地处理地理相关数据。请参考相关文档开启。</span>
                    </div>
                    <!-- 已启用 PostGIS -->
                    <template v-else>
                      <el-form-item label="计算后端">
                        <el-radio-group v-model="config.spatial_backend">
                          <el-radio value="auto">自动检测</el-radio>
                          <el-radio value="python">Python (兼容所有数据库)</el-radio>
                          <el-radio value="postgis">PostGIS</el-radio>
                        </el-radio-group>
                        <div class="radio-hint">
                          <template v-if="config.spatial_backend === 'auto'">
                            自动检测数据库能力，PostgreSQL + PostGIS 环境自动使用高性能实现
                          </template>
                          <template v-else-if="config.spatial_backend === 'python'">
                            使用 Python 计算，兼容所有数据库但性能较低
                          </template>
                          <template v-else>
                            使用 PostGIS 空间函数，高性能
                          </template>
                        </div>
                      </el-form-item>

                      <!-- PostGIS 几何数据同步 -->
                      <el-form-item v-if="databaseInfo?.database_type === 'postgresql' && databaseInfo?.postgis_enabled && (config.spatial_backend === 'postgis' || config.spatial_backend === 'auto')" label="PostGIS 几何数据">
                        <div v-if="postgisSyncStatusLoading" class="postgis-sync-loading">
                          <el-icon class="is-loading"><Loading /></el-icon>
                          <span>加载状态中...</span>
                        </div>
                        <div v-else class="postgis-sync-status">
                          <div class="sync-status-item">
                            <span class="status-label">几何数据 (geometry):</span>
                            <span class="status-value">{{ postgisSyncStatus.has_geometry || 0 }} 条</span>
                          </div>
                          <div class="sync-status-item">
                            <span class="status-label">PostGIS 空间表:</span>
                            <span class="status-value">{{ postgisSyncStatus.has_postgis || 0 }} 条</span>
                          </div>
                          <div v-if="postgisSyncStatus.need_sync > 0" class="sync-status-item need-sync">
                            <span class="status-label">需要同步:</span>
                            <span class="status-value">{{ postgisSyncStatus.need_sync }} 条</span>
                          </div>
                          <el-button
                            type="primary"
                            @click="syncPostGISGeometry"
                            :loading="syncingPostGIS"
                            :disabled="postgisSyncStatus.need_sync === 0"
                          >
                            {{ syncingPostGIS ? '同步中...' : '同步到 PostGIS' }}
                          </el-button>
                          <div v-if="postgisSyncProgress.show" class="sync-progress">
                            <el-progress
                              :percentage="postgisSyncProgress.percentage"
                              :status="postgisSyncProgress.status"
                            />
                            <span class="progress-text">{{ postgisSyncProgress.text }}</span>
                          </div>
                        </div>
                      </el-form-item>
                    </template>
                  </div>

                  <!-- 道路标志缓存 -->
                  <div class="form-section">
                    <div class="section-title">道路标志缓存</div>
                    <el-form-item label="清除缓存">
                      <el-button @click="clearRoadSignCache('way')" :loading="clearingWayCache">
                        清除普通道路缓存
                      </el-button>
                      <el-button @click="clearRoadSignCache('expwy')" :loading="clearingExpwyCache">
                        清除高速公路缓存
                      </el-button>
                      <el-button type="danger" @click="clearRoadSignCache()" :loading="clearingAllCache">
                        清除全部缓存
                      </el-button>
                    </el-form-item>
                  </div>

                  <el-form-item>
                    <el-button type="primary" @click="saveConfig" :loading="saving">保存配置</el-button>
                    <el-button @click="loadConfig">重置</el-button>
                  </el-form-item>
                </el-form>
              </el-card>
            </div>
          </el-tab-pane>

          <!-- 用户管理 -->
          <el-tab-pane label="用户管理" name="users">
            <!-- 搜索、排序、筛选栏 -->
            <el-card shadow="never" class="filter-card">
              <el-row :gutter="12">
                <!-- 搜索 -->
                <el-col :xs="24" :sm="12" :md="8">
                  <el-input v-model="userSearchQuery" placeholder="搜索用户名或邮箱..." :prefix-icon="Search" clearable
                    @input="handleUserSearch" />
                </el-col>
                <!-- 排序 -->
                <el-col :xs="12" :sm="12" :md="8">
                  <div class="sort-buttons">
                    <el-button v-for="item in userSortOptions" :key="item.value"
                      :type="userSortBy === item.value ? 'primary' : ''" @click="handleUserSortClick(item.value)">
                      {{ item.label }}
                      <el-icon v-if="userSortBy === item.value" class="sort-icon">
                        <component :is="userSortOrder === 'desc' ? ArrowDown : ArrowUp" />
                      </el-icon>
                    </el-button>
                  </div>
                </el-col>
                <!-- 筛选 -->
                <el-col :xs="12" :sm="12" :md="8">
                  <div class="filter-buttons">
                    <el-popover placement="bottom-end" :width="260" trigger="click">
                      <template #reference>
                        <el-button :type="hasActiveFilters ? 'primary' : ''">
                          筛选
                          <el-icon class="el-icon--right">
                            <ArrowDown />
                          </el-icon>
                        </el-button>
                      </template>
                      <div class="filter-popover-content">
                        <div class="filter-section">
                          <span class="filter-label">角色：</span>
                          <el-checkbox-group v-model="userRoleFilters" @change="loadUsersImmediate">
                            <el-checkbox-button label="admin">管理员</el-checkbox-button>
                            <el-checkbox-button label="user">普通用户</el-checkbox-button>
                          </el-checkbox-group>
                        </div>
                        <el-divider style="margin: 12px 0" />
                        <div class="filter-section">
                          <span class="filter-label">状态：</span>
                          <el-checkbox-group v-model="userStatusFilters" @change="loadUsersImmediate">
                            <el-checkbox-button label="active">正常</el-checkbox-button>
                            <el-checkbox-button label="inactive">已禁用</el-checkbox-button>
                          </el-checkbox-group>
                        </div>
                        <el-divider style="margin: 12px 0" />
                        <div class="filter-actions">
                          <el-button size="small" style="width: 100%" @click="resetFiltersAndClose">重置筛选</el-button>
                        </div>
                      </div>
                    </el-popover>
                  </div>
                </el-col>
              </el-row>
            </el-card>

            <!-- 加载中显示骨架屏 -->
            <div v-if="loadingUsers" class="list-skeleton">
              <el-skeleton :rows="5" animated />
            </div>

            <!-- 加载完成后显示内容 -->
            <el-card v-else class="list-card" shadow="never">
              <!-- 桌面端表格 -->
              <el-table :data="users" class="pc-table" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="username" label="用户名" min-width="150" />
                <el-table-column prop="email" label="邮箱" min-width="200">
                  <template #default="{ row }">
                    {{ row.email || '-' }}
                  </template>
                </el-table-column>
                <el-table-column label="角色" width="120">
                  <template #default="{ row }">
                    <el-tag :type="row.is_admin ? 'danger' : 'primary'" size="small">
                      {{ row.is_admin ? '管理员' : '普通用户' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                      {{ row.is_active ? '正常' : '已禁用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ formatDateTime(row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="280" fixed="right">
                  <template #default="{ row }">
                    <el-button v-if="!row.is_admin && !isCurrentUser(row) && !isFirstUser(row)" type="primary"
                      size="small" text @click="toggleUserAdmin(row)">
                      设为管理员
                    </el-button>
                    <el-button v-else type="info" size="small" text :disabled="isCurrentUser(row) || isFirstUser(row)">
                      {{ row.is_admin ? '已是管理员' : '不可操作' }}
                    </el-button>
                    <el-button v-if="row.is_active && !isCurrentUser(row) && !isFirstUser(row)" type="warning"
                      size="small" text @click="toggleUserActive(row)">
                      禁用
                    </el-button>
                    <el-button v-else-if="!row.is_active && !isCurrentUser(row) && !isFirstUser(row)" type="success"
                      size="small" text @click="toggleUserActive(row)">
                      启用
                    </el-button>
                    <el-button v-else type="info" size="small" text disabled>
                      {{ row.is_active ? '不可操作' : '不可操作' }}
                    </el-button>
                    <el-button v-if="!isCurrentUser(row) && !isFirstUser(row)" type="info" size="small" text
                      @click="showResetPasswordDialog(row)">
                      重置密码
                    </el-button>
                    <el-button v-if="!isCurrentUser(row) && !isFirstUser(row)" type="danger" size="small" text
                      @click="deleteUser(row)">
                      删除
                    </el-button>
                    <el-button v-else type="info" size="small" text disabled>
                      不可操作
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 移动端卡片列表 -->
              <div class="mobile-card-list">
                <div v-for="user in users" :key="user.id" class="mobile-user-card">
                  <div class="mobile-card-header">
                    <span class="mobile-card-title">{{ user.username }}</span>
                    <div>
                      <el-tag :type="user.is_admin ? 'danger' : 'primary'" size="small">
                        {{ user.is_admin ? '管理员' : '普通用户' }}
                      </el-tag>
                      <el-tag :type="user.is_active ? 'success' : 'info'" size="small" style="margin-left: 4px">
                        {{ user.is_active ? '正常' : '已禁用' }}
                      </el-tag>
                    </div>
                  </div>
                  <div class="mobile-card-body">
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">ID</span>
                      <span class="mobile-card-value">{{ user.id }}</span>
                    </div>
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">邮箱</span>
                      <span class="mobile-card-value">{{ user.email || '-' }}</span>
                    </div>
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">创建时间</span>
                      <span class="mobile-card-value">{{ formatDateTime(user.created_at) }}</span>
                    </div>
                  </div>
                  <div class="mobile-card-actions">
                    <el-button v-if="!user.is_admin && !isCurrentUser(user) && !isFirstUser(user)" type="primary"
                      size="small" @click="toggleUserAdmin(user)">
                      设为管理员
                    </el-button>
                    <el-button v-if="user.is_active && !isCurrentUser(user) && !isFirstUser(user)" type="warning"
                      size="small" @click="toggleUserActive(user)">
                      禁用
                    </el-button>
                    <el-button v-else-if="!user.is_active && !isCurrentUser(user) && !isFirstUser(user)" type="success"
                      size="small" @click="toggleUserActive(user)">
                      启用
                    </el-button>
                    <el-button v-if="!isCurrentUser(user) && !isFirstUser(user)" type="info" size="small"
                      @click="showResetPasswordDialog(user)">
                      重置密码
                    </el-button>
                    <el-button v-if="!isCurrentUser(user) && !isFirstUser(user)" type="danger" size="small"
                      @click="deleteUser(user)">
                      删除
                    </el-button>
                    <el-button v-if="isCurrentUser(user) || isFirstUser(user)" type="info" size="small" disabled>
                      不可操作
                    </el-button>
                  </div>
                </div>
              </div>
            </el-card>

            <!-- 分页 -->
            <div class="pagination" v-if="users.length > 0">
              <el-pagination v-model:current-page="usersCurrentPage" v-model:page-size="usersPageSize"
                :page-sizes="[10, 20, 50, 100]" :total="usersTotal"
                :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
                @current-change="loadUsers" @size-change="loadUsers" />
            </div>
          </el-tab-pane>

          <!-- 邀请码管理 -->
          <el-tab-pane label="邀请码" name="invite-codes">
            <!-- 加载中显示骨架屏 -->
            <div v-if="loadingInviteCodes" class="list-skeleton">
              <el-skeleton :rows="5" animated />
            </div>

            <!-- 加载完成后显示内容 -->
            <el-card v-else class="list-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>邀请码列表</span>
                  <el-button type="primary" :icon="Plus" @click="showCreateInviteCodeDialog">
                    创建邀请码
                  </el-button>
                </div>
              </template>

              <!-- 桌面端表格 -->
              <el-table :data="inviteCodes" class="pc-table" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="code" label="邀请码" min-width="150">
                  <template #default="{ row }">
                    <el-tag>{{ row.code }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="使用情况" width="150">
                  <template #default="{ row }">
                    {{ row.used_count }} / {{ row.max_uses }}
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="getInviteCodeStatus(row).type" size="small">
                      {{ getInviteCodeStatus(row).text }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="expires_at" label="过期时间" width="180">
                  <template #default="{ row }">
                    {{ row.expires_at ? formatDateTime(row.expires_at) : '永久有效' }}
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ formatDateTime(row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100" fixed="right">
                  <template #default="{ row }">
                    <el-button v-if="row.is_valid" type="danger" size="small" text @click="deleteInviteCode(row)">
                      删除
                    </el-button>
                    <el-button v-else type="info" size="small" text disabled>
                      已删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 移动端卡片列表 -->
              <div class="mobile-card-list">
                <div v-for="inviteCode in inviteCodes" :key="inviteCode.id" class="mobile-invite-card">
                  <div class="mobile-card-header">
                    <span class="invite-code-display">{{ inviteCode.code }}</span>
                    <el-tag :type="getInviteCodeStatus(inviteCode).type" size="small">
                      {{ getInviteCodeStatus(inviteCode).text }}
                    </el-tag>
                  </div>
                  <div class="mobile-card-body">
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">使用情况</span>
                      <span class="mobile-card-value">{{ inviteCode.used_count }} / {{ inviteCode.max_uses }}</span>
                    </div>
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">过期时间</span>
                      <span class="mobile-card-value">{{ inviteCode.expires_at ? formatDateTime(inviteCode.expires_at) :
                        '永久有效' }}</span>
                    </div>
                    <div class="mobile-card-row">
                      <span class="mobile-card-label">创建时间</span>
                      <span class="mobile-card-value">{{ formatDateTime(inviteCode.created_at) }}</span>
                    </div>
                  </div>
                  <div class="mobile-card-actions">
                    <el-button v-if="inviteCode.is_valid" type="danger" size="small"
                      @click="deleteInviteCode(inviteCode)">
                      删除
                    </el-button>
                    <el-button v-else type="info" size="small" disabled>
                      已删除
                    </el-button>
                  </div>
                </div>
              </div>
            </el-card>

            <!-- 分页 -->
            <div class="pagination" v-if="inviteCodes.length > 0">
              <el-pagination v-model:current-page="inviteCodesCurrentPage" v-model:page-size="inviteCodesPageSize"
                :page-sizes="[10, 20, 50, 100]" :total="inviteCodesTotal"
                :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
                @current-change="loadInviteCodes" @size-change="loadInviteCodes" />
            </div>
          </el-tab-pane>

          <!-- 字体管理 -->
          <el-tab-pane label="字体管理" name="fonts">
            <div class="fonts-tab-content">
              <!-- 加载中显示骨架屏 -->
              <div v-if="loadingFonts" class="fonts-skeleton">
                <el-skeleton :rows="8" animated />
              </div>

              <!-- 加载完成后显示内容 -->
              <template v-else>
                <!-- 激活字体选择 -->
                <el-card shadow="never" style="margin-bottom: 16px;">
                  <template #header>
                    <span>激活字体选择</span>
                  </template>
                  <el-row :gutter="16">
                    <el-col :xs="24" :sm="8">
                      <div class="font-selector-item">
                        <div class="font-selector-label">A 型字体</div>
                        <div class="font-selector-desc">用于中文标题（如"国家高速"、"京"）</div>
                        <el-select :model-value="activeFonts.font_a" @change="(val) => setActiveFont('a', val)"
                          placeholder="选择 A 型字体" style="width: 100%">
                          <el-option v-for="font in fonts" :key="font.filename" :label="font.filename"
                            :value="font.filename" />
                        </el-select>
                      </div>
                    </el-col>
                    <el-col :xs="24" :sm="8">
                      <div class="font-selector-item">
                        <div class="font-selector-label">B 型字体</div>
                        <div class="font-selector-desc">用于主数字（如"G5"、"45"）</div>
                        <el-select :model-value="activeFonts.font_b" @change="(val) => setActiveFont('b', val)"
                          placeholder="选择 B 型字体" style="width: 100%">
                          <el-option v-for="font in fonts" :key="font.filename" :label="font.filename"
                            :value="font.filename" />
                        </el-select>
                      </div>
                    </el-col>
                    <el-col :xs="24" :sm="8">
                      <div class="font-selector-item">
                        <div class="font-selector-label">C 型字体</div>
                        <div class="font-selector-desc">用于小数字（如"01"）</div>
                        <el-select :model-value="activeFonts.font_c" @change="(val) => setActiveFont('c', val)"
                          placeholder="选择 C 型字体" style="width: 100%">
                          <el-option v-for="font in fonts" :key="font.filename" :label="font.filename"
                            :value="font.filename" />
                        </el-select>
                      </div>
                    </el-col>
                  </el-row>
                  <el-alert v-if="!activeFonts.font_a || !activeFonts.font_b || !activeFonts.font_c" type="warning"
                    :closable="false" style="margin-top: 12px;">
                    字体未完整配置，道路标志生成功能将被禁用
                  </el-alert>
                </el-card>
              </template>

              <!-- 字体文件列表 -->
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>字体文件列表</span>
                    <el-upload :auto-upload="false" :show-file-list="false" :on-change="handleFontUpload"
                      accept=".ttf,.otf,.ttc">
                      <el-button type="primary" :icon="Plus">上传字体</el-button>
                    </el-upload>
                  </div>
                </template>

                <!-- 桌面端表格 -->
                <el-table :data="fonts" class="pc-table" style="width: 100%">
                  <el-table-column prop="filename" label="文件名" min-width="200" />
                  <el-table-column label="大小" width="120">
                    <template #default="{ row }">
                      {{ formatFileSize(row.size) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="150" fixed="right">
                    <template #default="{ row }">
                      <el-button type="danger" size="small" text @click="deleteFont(row)">
                        删除
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- 移动端卡片列表 -->
                <div class="mobile-card-list">
                  <div v-for="font in fonts" :key="font.filename" class="mobile-font-card">
                    <div class="mobile-card-header">
                      <span class="mobile-card-title">{{ font.filename }}</span>
                    </div>
                    <div class="mobile-card-body">
                      <div class="mobile-card-row">
                        <span class="mobile-card-label">大小</span>
                        <span class="mobile-card-value">{{ formatFileSize(font.size) }}</span>
                      </div>
                    </div>
                    <div class="mobile-card-actions">
                      <el-button type="danger" size="small" @click="deleteFont(font)">
                        删除
                      </el-button>
                    </div>
                  </div>
                </div>
              </el-card>
            </div>
          </el-tab-pane>

          <!-- 特殊地名映射（仅 GDF 地理编码时显示） -->
          <el-tab-pane v-if="config.geocoding_provider === 'gdf'" label="地名映射" name="place-mapping">
            <div class="place-mapping-tab-content">
              <el-card shadow="never" class="mapping-card">
                <template #header>
                  <div class="card-header-with-actions">
                    <span>特殊地名英文映射表</span>
                    <div class="header-actions">
                      <el-button size="small" @click="loadMappings">重新加载</el-button>
                      <el-button size="small" :type="yamlValidationErrors.length > 0 ? 'danger' : 'primary'"
                        :loading="savingMapping" :disabled="yamlValidationErrors.length > 0" @click="saveMappingsFromYaml">
                        {{ yamlValidationErrors.length > 0 ? '格式有误' : '保存' }}
                      </el-button>
                    </div>
                  </div>
                </template>

                <div class="mapping-description">
                  <p>用于处理多音字和少数民族聚居区地名的英文转写。</p>
                  <p>格式：YAML 格式，<code>中文名称: 英文名称</code>。支持两种格式：</p>
                  <p>• 完整名称（含空格）：直接使用，如 <code>延边朝鲜族自治州: Yanbian Korean Autonomous Prefecture</code></p>
                  <p>• 基础名称（无空格）：自动添加后缀，如 <code>北京市: Beijing</code> → <code>Beijing Municipality</code></p>
                </div>

                <div class="mapping-editor-wrapper">
                  <CodeMirrorYamlEditor v-model="mappingYaml" :min-height="'calc(100vh - 320px)'"
                    @valid="handleYamlValidation" />
                </div>
              </el-card>
            </div>
          </el-tab-pane>

          <!-- 边界数据管理（已弃用，保留代码但不显示） -->
          <!-- @deprecated 此功能已被 DataV GeoJSON 在线导入取代，保留代码以备不时之需 -->
          <el-tab-pane v-if="false" label="边界数据" name="bounds-data">
            <div class="bounds-data-tab-content">
              <!-- 边界数据导入 -->
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>边界数据导入</span>
                  </div>
                </template>

                <!-- 上传区域 -->
                <el-upload class="bounds-upload" drag :auto-upload="false" :show-file-list="false"
                  :on-change="handleBoundsFileChange" accept=".zip,.rar">
                  <el-icon class="el-icon--upload">
                    <UploadFilled />
                  </el-icon>
                  <div class="el-upload__text">
                    拖拽文件到此处或 <em>点击上传</em>
                  </div>
                  <template #tip>
                    <div class="el-upload__tip">
                      支持 ZIP 或 RAR 格式，文件应包含 GeoJSON 数据
                    </div>
                  </template>
                </el-upload>

                <!-- 文件信息 -->
                <div v-if="selectedBoundsFile" class="selected-file-info">
                  <el-descriptions :column="2" border>
                    <el-descriptions-item label="文件名">{{ selectedBoundsFile.name }}</el-descriptions-item>
                    <el-descriptions-item label="文件大小">{{ formatFileSize(selectedBoundsFile.size)
                      }}</el-descriptions-item>
                  </el-descriptions>
                  <el-button type="primary" :loading="importingBounds" :disabled="boundsImportPolling"
                    @click="importBoundsData" style="margin-top: 16px">
                    {{ boundsImportPolling ? '处理中...' : '导入边界数据' }}
                  </el-button>
                  <el-button @click="selectedBoundsFile = null" :disabled="boundsImportPolling"
                    style="margin-top: 16px">
                    清除
                  </el-button>
                </div>

                <!-- 导入进度 -->
                <div v-if="boundsImportTask"
                  :class="['import-progress', `import-progress--${boundsImportTask.status}`]">
                  <el-alert
                    :type="boundsImportTask.status === 'failed' ? 'error' : boundsImportTask.status === 'completed' ? 'success' : 'info'"
                    :closable="false" show-icon>
                    <template #title>
                      {{ boundsImportTask.status === 'running' ? '正在后台处理' : boundsImportTask.status === 'completed' ?
                        '导入完成' : boundsImportTask.status === 'failed' ? '导入失败' : '处理中' }}
                    </template>
                  </el-alert>
                  <div style="margin-top: 16px">
                    <el-progress :percentage="boundsImportTask.progress"
                      :status="boundsImportTask.status === 'failed' ? 'exception' : boundsImportTask.status === 'completed' ? 'success' : undefined" />
                  </div>
                  <div v-if="boundsImportTask.result_path" class="result-summary">
                    {{ boundsImportTask.result_path }}
                  </div>
                  <div v-if="boundsImportTask.error_message" class="error-message">
                    {{ boundsImportTask.error_message }}
                  </div>
                </div>
              </el-card>

              <!-- 边界数据统计 -->
              <el-card shadow="never">
                <template #header>
                  <div class="card-header">
                    <span>边界数据统计</span>
                    <el-button @click="loadBoundsStats" :loading="loadingBoundsStats" size="small">
                      刷新统计
                    </el-button>
                  </div>
                </template>

                <div v-if="boundsStats" class="bounds-stats-section">
                  <div class="section-description">仅供参考。其中包括功能区，并非传统意义上的行政区划。</div>
                  <h4>按层级统计</h4>
                  <el-table :data="formatBoundsStats()" stripe class="bounds-stats">
                    <el-table-column prop="level" label="层级" />
                    <el-table-column prop="total" label="总计" />
                    <el-table-column prop="with_bounds" label="有边界框" />
                    <el-table-column label="覆盖率">
                      <template #default="{ row }">
                        {{ ((row.with_bounds / row.total) * 100).toFixed(1) }}%
                      </template>
                    </el-table-column>
                  </el-table>

                  <h4 style="margin-top: 24px">缺少边界框（前10省）</h4>
                  <el-table :data="boundsStats.missing_by_province" stripe class="bounds-stats">
                    <el-table-column prop="province_name" label="省份名称" min-width="20%" />
                    <el-table-column prop="province_code" label="省份代码" min-width="20%" />
                    <el-table-column prop="missing_count" label="缺少数量" min-width="20%" />
                    <el-table-column prop="missing_areas" label="缺少地区" />
                  </el-table>
                </div>
              </el-card>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-main>
    </el-container>

    <!-- 创建邀请码对话框 -->
    <el-dialog v-model="createInviteCodeDialogVisible" title="创建邀请码" :width="isMobile ? '95%' : '500px'"
      class="responsive-dialog">
      <el-form :model="inviteCodeForm" label-width="120px" class="dialog-form">
        <el-form-item label="邀请码">
          <el-input v-model="inviteCodeForm.code" placeholder="留空自动生成" />
          <span class="form-tip">留空则自动生成随机邀请码</span>
        </el-form-item>
        <el-form-item label="最大使用次数">
          <el-input-number v-model="inviteCodeForm.max_uses" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="有效期（天）">
          <el-input-number v-model="inviteCodeForm.expires_in_days" :min="1" :max="365" />
          <span class="form-tip">留空则永久有效</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createInviteCodeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingInviteCode" @click="createInviteCode">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetPasswordDialogVisible" title="重置密码" :width="isMobile ? '95%' : '500px'"
      class="responsive-dialog">
      <el-form :model="resetPasswordForm" label-width="100px" class="dialog-form">
        <el-form-item label="用户名">
          <el-input :value="resetPasswordForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="resetPasswordForm.new_password" type="password" placeholder="请输入新密码（至少 6 位）" show-password
            clearable />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="resetPasswordForm.confirm_password" type="password" placeholder="请再次输入新密码" show-password
            clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resettingPassword" @click="confirmResetPassword">
          确认重置
        </el-button>
      </template>
    </el-dialog>

    <!-- 未保存更改确认对话框 -->
    <el-dialog v-model="unsavedChangesDialogVisible" title="提示" :width="isMobile ? '90%' : '420px'"
      class="unsaved-changes-dialog">
      <p>系统配置有未保存的更改，确定要离开吗？</p>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleUnsavedChanges('cancel')">取消</el-button>
          <el-button type="primary" @click="handleUnsavedChanges('save')">保存配置</el-button>
          <el-button type="danger" @click="handleUnsavedChanges('leave')">离开</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 行政区划数据统计对话框 -->
    <el-dialog v-model="divisionStatsDialogVisible" title="行政区划数据统计" :width="isMobile ? '95%' : '600px'">
      <div v-if="divisionStats" class="division-stats">
        <div v-if="divisionStats.error" class="stats-error">
          <el-icon>
            <InfoFilled />
          </el-icon>
          <span>{{ divisionStats.error }}</span>
        </div>
        <template v-else>
          <div class="stat-row">
            <span class="stat-label">总记录数:</span>
            <span class="stat-value">{{ divisionStats.total }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">省级:</span>
            <span class="stat-value">{{ divisionStats.by_level.province }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">市级:</span>
            <span class="stat-value">{{ divisionStats.by_level.city }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">区县级:</span>
            <span class="stat-value">{{ divisionStats.by_level.area }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">有边界框:</span>
            <span class="stat-value">{{ divisionStats.has_bounds }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">有 PostGIS 几何:</span>
            <span class="stat-value">{{ divisionStats.has_postgis }}</span>
          </div>
          <div v-if="divisionStats.sample_missing_codes.length > 0" class="missing-codes">
            <div class="missing-title">缺少关联代码的区县记录（前5条）:</div>
            <div v-for="item in divisionStats.sample_missing_codes" :key="item.code" class="missing-item">
              {{ item.name }} ({{ item.code }}) - city_code: {{ item.city_code || '无' }}, province_code: {{
                item.province_code || '无' }}
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="divisionStatsDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, onUnmounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, HomeFilled, User as UserIcon, ArrowDown, SwitchButton, List, Plus, Rank, ArrowUp, Search, InfoFilled, UploadFilled } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import { adminApi, type SystemConfig, type User, type InviteCode, type MapLayerConfig, type CRSType, type FontInfo, type FontConfig, type DatabaseInfo, type AdminDivisionStats, type SpecialPlaceMappingResponse, type BoundsStatsResponse, type BoundsImportTask, type AdminDivisionStatusResponse, type ImportTaskProgress } from '@/api/admin'
import { roadSignApi } from '@/api/roadSign'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/format'
import { useConfigStore } from '@/stores/config'
import { hashPassword } from '@/utils/crypto'
import CodeMirrorYamlEditor from '@/components/CodeMirrorYamlEditor.vue'

const router = useRouter()
const authStore = useAuthStore()
const configStore = useConfigStore()

// 检查管理员权限
if (!authStore.user?.is_admin) {
  ElMessage.error('需要管理员权限')
  router.push('/')
}

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value <= 1366)

// 监听窗口大小变化
function handleResize() {
  screenWidth.value = window.innerWidth
}

const activeTab = ref('config')
const loadingConfig = ref(false)
const loadingUsers = ref(false)
const loadingInviteCodes = ref(false)
const loadingDivisionStats = ref(false)
const divisionStatsDialogVisible = ref(false)
const divisionStats = ref<AdminDivisionStats | null>(null)
const loadingFonts = ref(false)
const saving = ref(false)
const creatingInviteCode = ref(false)
const uploadingFont = ref(false)

// 特殊地名映射
const mappingYaml = ref('')
const loadingMapping = ref(false)
const yamlValidationErrors = ref<string[]>([])

// YAML 格式校验处理
function handleYamlValidation(isValid: boolean, errors: string[]) {
  yamlValidationErrors.value = errors
}
const savingMapping = ref(false)
const regeneratingNameEn = ref(false)
const mappingStats = ref<{ total: number } | null>(null)

// 边界数据管理
const selectedBoundsFile = ref<File | null>(null)
const importingBounds = ref(false)
const boundsImportTask = ref<{ id: number; status: string; progress: number; result_path?: string; error_message?: string } | null>(null)
const boundsImportPolling = ref(false)
const loadingBoundsStats = ref(false)
const boundsStats = ref<BoundsStatsResponse | null>(null)

// DataV GeoJSON 行政区划导入
const datavImportMode = ref<'full' | 'bounds' | 'provinces'>('full')
const datavForceOverwrite = ref(false)
const datavSelectedProvinces = ref<string[]>([])
const datavProvinceList = ref<Array<{ code: string; name: string }>>([])
const loadingProvinces = ref(false)
const datavImporting = ref(false)
const datavImportTaskId = ref<number | null>(null)
const datavImportProgress = ref<ImportTaskProgress | null>(null)
const datavUploadFile = ref<File | null>(null)
const datavDivisionStatus = ref<AdminDivisionStatusResponse | null>(null)
const loadingDivisionStatus = ref(false)

// 标记组件是否已挂载，用于避免卸载后更新状态
const isMounted = ref(true)

// 道路标志缓存清除状态
const clearingWayCache = ref(false)
const clearingExpwyCache = ref(false)
const clearingAllCache = ref(false)

// 用户管理分页
const usersTotal = ref(0)
const usersCurrentPage = ref(1)
const usersPageSize = ref(20)

// 邀请码管理分页
const inviteCodesTotal = ref(0)
const inviteCodesCurrentPage = ref(1)
const inviteCodesPageSize = ref(20)

// 用户搜索、排序、筛选
const userSearchQuery = ref('')
const adminCount = ref(0)  // 管理员数量统计
const userSortBy = ref('created_at')
const userSortOrder = ref<'asc' | 'desc'>('desc')  // 默认降序（最新在前）
const userSortOptions = [
  { label: '创建时间', value: 'created_at' },
  { label: '用户名', value: 'username' },
  { label: '邮箱', value: 'email' },
]
const userRoleFilters = ref<string[]>(['admin', 'user'])  // 默认全选
const userStatusFilters = ref<string[]>(['active'])  // 默认正常状态

// 重置密码
const resetPasswordDialogVisible = ref(false)
const resettingPassword = ref(false)
const resetPasswordForm = reactive({
  user_id: 0,
  username: '',
  new_password: '',
  confirm_password: '',
})

// 未保存更改对话框
const unsavedChangesDialogVisible = ref(false)
let unsavedChangesResolve: ((action: 'save' | 'leave' | 'cancel') => void) | null = null

// 显示未保存更改对话框，返回用户选择的操作
function showUnsavedChangesDialog(): Promise<'save' | 'leave' | 'cancel'> {
  return new Promise((resolve) => {
    unsavedChangesResolve = resolve
    unsavedChangesDialogVisible.value = true
  })
}

// 处理用户选择
function handleUnsavedChanges(action: 'save' | 'leave' | 'cancel') {
  unsavedChangesDialogVisible.value = false
  if (unsavedChangesResolve) {
    unsavedChangesResolve(action)
    unsavedChangesResolve = null
  }
}

// 系统配置
const config = reactive<SystemConfig>({
  registration_enabled: true,
  invite_code_required: false,
  show_road_sign_in_region_tree: true,
  default_map_provider: 'osm',
  geocoding_provider: 'gdf',  // 默认使用本地地理编码
  geocoding_config: {
    nominatim: { url: '', email: '' },
    gdf: {},
    amap: { api_key: '', freq: 3 },
    baidu: { api_key: '', freq: 3, get_en_result: false },
  },
  map_layers: {},
  spatial_backend: 'auto',
  allow_server_poster: true,  // 默认允许服务器生成海报
})

// 所有地图层列表（按固定顺序）
const allMapLayers = ref<MapLayerConfig[]>([])

// 原始配置（用于检测未保存的更改）
const originalConfig = ref<SystemConfig | null>(null)

// 数据库信息（用于判断是否显示 PostGIS 设置）
const databaseInfo = ref<DatabaseInfo | null>(null)

// PostGIS 同步状态
const postgisSyncStatus = ref<{
  has_geometry: number
  has_postgis: number
  need_sync: number
  postgis_enabled: boolean
  spatial_table_exists: boolean
}>({
  has_geometry: 0,
  has_postgis: 0,
  need_sync: 0,
  postgis_enabled: false,
  spatial_table_exists: false,
})
const postgisSyncStatusLoading = ref(false)
const syncingPostGIS = ref(false)
const postgisSyncProgress = ref<{
  show: boolean
  percentage: number
  status: '' | 'success' | 'exception'
  text: string
}>({
  show: false,
  percentage: 0,
  status: '',
  text: '',
})
let postgisSyncTaskId: number | null = null
let postgisSyncTimer: ReturnType<typeof setInterval> | null = null

// 用户列表
const users = ref<User[]>([])

// 邀请码列表
const inviteCodes = ref<InviteCode[]>([])
const createInviteCodeDialogVisible = ref(false)
const inviteCodeForm = reactive({
  code: '',
  max_uses: 1,
  expires_in_days: undefined as number | undefined,
})

// 字体列表
const fonts = ref<FontInfo[]>([])
const activeFonts = ref<FontConfig>({ font_a: undefined, font_b: undefined, font_c: undefined })

// 检测系统配置是否有未保存的更改
function hasUnsavedConfigChanges(): boolean {
  if (!originalConfig.value) return false
  // 比较当前配置和原始配置
  const currentConfig = JSON.parse(JSON.stringify(config))
  return JSON.stringify(currentConfig) !== JSON.stringify(originalConfig.value)
}

// 初始化 geocoding_config
function initGeocodingConfig() {
  if (!config.geocoding_config) {
    config.geocoding_config = {}
  }
  if (!config.geocoding_config.nominatim) {
    config.geocoding_config.nominatim = { url: 'http://localhost:8080' }
  }
  // GDF 不需要配置，使用 spatial_backend
  if (!config.geocoding_config.amap) {
    config.geocoding_config.amap = { api_key: '', freq: 3 }
  }
  if (!config.geocoding_config.baidu) {
    config.geocoding_config.baidu = { api_key: '', freq: 3, get_en_result: false }
  }
}

// 加载系统配置
async function loadConfig() {
  loadingConfig.value = true
  try {
    const data = await adminApi.getConfig()
    if (!isMounted.value) return
    Object.assign(config, data)
    initGeocodingConfig()
    // 初始化地图层列表（按固定顺序）
    initMapLayers()
    // 保存原始配置（深拷贝），用于检测未保存的更改
    originalConfig.value = JSON.parse(JSON.stringify(config))
    // 获取数据库信息（用于判断是否显示 PostGIS 设置）
    const dbInfo = await adminApi.getDatabaseInfo()
    if (isMounted.value) {
      databaseInfo.value = dbInfo
    }
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingConfig.value = false
    }
  }
}

// 清除道路标志缓存
async function clearRoadSignCache(signType?: 'way' | 'expwy') {
  // 确认操作
  const typeText = signType === 'way' ? '普通道路' : signType === 'expwy' ? '高速公路' : '全部'
  try {
    await ElMessageBox.confirm(
      `确定要清除${typeText}的道路标志缓存吗？这将删除所有已生成的标志文件。`,
      '确认清除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return // 用户取消
  }

  // 设置对应的加载状态
  if (signType === 'way') {
    clearingWayCache.value = true
  } else if (signType === 'expwy') {
    clearingExpwyCache.value = true
  } else {
    clearingAllCache.value = true
  }

  try {
    const result = await roadSignApi.clearCache(signType)
    ElMessage.success(`已清除 ${result.count} 个缓存`)
  } finally {
    // 重置加载状态
    clearingWayCache.value = false
    clearingExpwyCache.value = false
    clearingAllCache.value = false
  }
}

// 获取 PostGIS 同步状态
async function loadPostgisSyncStatus() {
  if (!databaseInfo.value?.postgis_enabled) {
    return
  }
  postgisSyncStatusLoading.value = true
  try {
    const response = await adminApi.getPostgisSyncStatus()
    if (isMounted.value) {
      postgisSyncStatus.value = response
    }
  } catch (error) {
    // 静默失败，可能不是 PostgreSQL
  } finally {
    if (isMounted.value) {
      postgisSyncStatusLoading.value = false
    }
  }
}

// 同步到 PostGIS
async function syncPostGISGeometry() {
  try {
    await ElMessageBox.confirm(
      '将 geometry 字段的数据同步到 PostGIS 空间表，这可能需要一些时间。是否继续？',
      '确认同步',
      {
        confirmButtonText: '开始同步',
        cancelButtonText: '取消',
        type: 'info',
      }
    )
  } catch {
    return // 用户取消
  }

  syncingPostGIS.value = true
  postgisSyncProgress.value = {
    show: true,
    percentage: 0,
    status: '',
    text: '创建同步任务...',
  }

  try {
    const response = await adminApi.syncPostgisGeometry()
    postgisSyncTaskId = response.task_id

    // 开始轮询任务进度
    postgisSyncProgress.value.text = '同步中...'
    pollPostgisSyncProgress()
  } catch (error) {
    syncingPostGIS.value = false
    postgisSyncProgress.value.show = false
    // 错误已在拦截器中处理
  }
}

// 轮询 PostGIS 同步进度
async function pollPostgisSyncProgress() {
  if (postgisSyncTaskId === null) return

  postgisSyncTimer = setInterval(async () => {
    try {
      const task = await adminApi.getTask(postgisSyncTaskId)

      if (task.is_finished) {
        clearInterval(postgisSyncTimer!)
        postgisSyncTimer = null

        if (task.status === 'completed') {
          postgisSyncProgress.value.percentage = 100
          postgisSyncProgress.value.status = 'success'
          postgisSyncProgress.value.text = '同步完成！'
          ElMessage.success('PostGIS 几何数据同步完成')

          // 刷新同步状态
          await loadPostgisSyncStatus()
        } else if (task.status === 'failed') {
          postgisSyncProgress.value.status = 'exception'
          postgisSyncProgress.value.text = '同步失败: ' + (task.error || '未知错误')
          ElMessage.error('同步失败: ' + (task.error || '未知错误'))
        }

        syncingPostGIS.value = false

        // 3秒后隐藏进度条
        setTimeout(() => {
          if (isMounted.value) {
            postgisSyncProgress.value.show = false
          }
        }, 3000)
      } else {
        // 更新进度
        postgisSyncProgress.value.percentage = task.progress || 0
      }
    } catch (error) {
      clearInterval(postgisSyncTimer!)
      postgisSyncTimer = null
      syncingPostGIS.value = false
      postgisSyncProgress.value.show = false
    }
  }, 1000)
}

// 初始化地图层列表
function initMapLayers() {
  if (!config.map_layers) {
    config.map_layers = {}
  }
  // 按 order 字段排序
  allMapLayers.value = Object.values(config.map_layers).sort((a: unknown, b: unknown) => (a as MapLayerConfig).order - (b as MapLayerConfig).order)
}

// 拖拽结束后的处理
function onDragEnd() {
  // 更新所有地图层的 order 值
  allMapLayers.value.forEach((layer: MapLayerConfig, index: number) => {
    layer.order = index
  })
}

// 判断是否为第一个地图层
function isFirstLayer(layer: MapLayerConfig): boolean {
  return allMapLayers.value[0]?.id === layer.id
}

// 判断是否为最后一个地图层
function isLastLayer(layer: MapLayerConfig): boolean {
  return allMapLayers.value[allMapLayers.value.length - 1]?.id === layer.id
}

// 上移地图层
function moveLayerUp(layer: MapLayerConfig) {
  const index = allMapLayers.value.findIndex((l: MapLayerConfig) => l.id === layer.id)
  if (index > 0) {
    // 交换位置
    const temp = allMapLayers.value[index - 1]
    allMapLayers.value[index - 1] = allMapLayers.value[index]
    allMapLayers.value[index] = temp
    // 更新 order 值
    allMapLayers.value.forEach((l: MapLayerConfig, i: number) => {
      l.order = i
    })
  }
}

// 下移地图层
function moveLayerDown(layer: MapLayerConfig) {
  const index = allMapLayers.value.findIndex((l: MapLayerConfig) => l.id === layer.id)
  if (index < allMapLayers.value.length - 1) {
    // 交换位置
    const temp = allMapLayers.value[index + 1]
    allMapLayers.value[index + 1] = allMapLayers.value[index]
    allMapLayers.value[index] = temp
    // 更新 order 值
    allMapLayers.value.forEach((l: MapLayerConfig, i: number) => {
      l.order = i
    })
  }
}

// 地图层切换事件
function onMapLayerToggle(layer: MapLayerConfig) {
  if (!layer.enabled) {
    // 如果禁用的是当前默认地图，需要切换默认地图
    if (layer.id === config.default_map_provider) {
      // 找到第一个启用的地图作为默认
      const firstEnabled = allMapLayers.value.find((l: MapLayerConfig) => l.enabled && l.id !== layer.id)
      if (firstEnabled) {
        config.default_map_provider = firstEnabled.id
      } else {
        // 如果没有其他启用的地图，不允许禁用
        layer.enabled = true
        ElMessage.warning('至少需要保留一个启用的地图')
      }
    }
  }
}

// 保存系统配置
async function saveConfig() {
  saving.value = true
  try {
    // 确保 map_layers 被正确保存
    const updateData: Partial<SystemConfig> = {
      ...config,
      map_layers: config.map_layers,
    }
    // 使用 configStore 的 updateConfig 方法，确保 publicConfig 也被更新
    await configStore.updateConfig(updateData)
    ElMessage.success('配置保存成功')
    // 保存成功后更新原始配置
    originalConfig.value = JSON.parse(JSON.stringify(config))
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
  }
}

// 地理编码提供商切换时初始化配置
function onGeocodingProviderChange() {
  initGeocodingConfig()
}

// 显示行政区划数据统计
async function showAdminDivisionStats() {
  loadingDivisionStats.value = true
  try {
    const response = await adminApi.getAdminDivisionStats()
    divisionStats.value = response
    divisionStatsDialogVisible.value = true
  } catch (error: any) {
    ElMessage.error(error?.message || '获取行政区划统计失败')
  } finally {
    loadingDivisionStats.value = false
  }
}

// ========== DataV GeoJSON 行政区划导入 ==========

// 加载行政区划状态
async function loadDivisionStatus() {
  loadingDivisionStatus.value = true
  try {
    datavDivisionStatus.value = await adminApi.getAdminDivisionStatus()
  } catch (error: any) {
    console.error('加载行政区划状态失败:', error)
  } finally {
    loadingDivisionStatus.value = false
  }
}

// 加载省份列表（用于按省份导入）
async function loadProvinceList() {
  if (datavProvinceList.value.length > 0) return  // 已加载
  loadingProvinces.value = true
  try {
    const response = await adminApi.getProvinceList()
    datavProvinceList.value = response.provinces
  } catch (error: any) {
    ElMessage.error('获取省份列表失败')
  } finally {
    loadingProvinces.value = false
  }
}

// 导入模式切换时加载省份列表
function onDatavImportModeChange() {
  if (datavImportMode.value === 'provinces') {
    loadProvinceList()
  }
}

// 从 DataV 在线导入
async function importFromDataVOnline() {
  // 如果是按省份导入但没选省份
  if (datavImportMode.value === 'provinces' && datavSelectedProvinces.value.length === 0) {
    ElMessage.warning('请至少选择一个省份')
    return
  }

  datavImporting.value = true
  datavImportProgress.value = null

  try {
    const response = await adminApi.importFromDataVOnline({
      province_codes: datavImportMode.value === 'provinces' ? datavSelectedProvinces.value : undefined,
      force: datavForceOverwrite.value,
      bounds_only: datavImportMode.value === 'bounds',
    })

    if (response.task_id) {
      datavImportTaskId.value = response.task_id
      ElMessage.success('导入任务已启动')
      // 开始轮询进度
      pollDatavImportProgress()
    } else {
      ElMessage.success(response.message)
      datavImporting.value = false
      // 刷新状态
      loadDivisionStatus()
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '启动导入任务失败')
    datavImporting.value = false
  }
}

// 上传压缩包导入
async function importFromUpload() {
  if (!datavUploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  datavImporting.value = true
  datavImportProgress.value = null

  try {
    const response = await adminApi.importFromUpload(datavUploadFile.value, datavForceOverwrite.value)

    if (response.task_id) {
      datavImportTaskId.value = response.task_id
      ElMessage.success('导入任务已启动')
      pollDatavImportProgress()
    } else {
      ElMessage.success(response.message)
      datavImporting.value = false
      datavUploadFile.value = null
      loadDivisionStatus()
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '上传导入失败')
    datavImporting.value = false
  }
}

// 轮询导入进度
let datavPollingTimer: ReturnType<typeof setTimeout> | null = null

async function pollDatavImportProgress() {
  if (!datavImportTaskId.value || !isMounted.value) return

  try {
    const progress = await adminApi.getImportProgress(datavImportTaskId.value)
    datavImportProgress.value = progress

    if (progress.is_finished) {
      datavImporting.value = false
      datavImportTaskId.value = null
      datavUploadFile.value = null

      if (progress.status === 'completed') {
        // 解析结果中的 PostGIS 同步信息
        const result = progress.result || progress.result_path || ''
        let message = '导入完成'
        if (result.includes('成功=') && result.includes('PostGIS')) {
          // 提取 PostGIS 同步结果
          const match = result.match(/成功=(\d+).*失败=(\d+)/)
          if (match) {
            message = `导入完成，PostGIS 同步：成功 ${match[1]} 条${match[2] > 0 ? `，失败 ${match[2]} 条` : ''}`
          }
        }
        ElMessage.success(message)
      } else if (progress.status === 'failed') {
        ElMessage.error(progress.error || '导入失败')
      }

      // 刷新状态
      loadDivisionStatus()
      // 如果是 PostgreSQL 环境，刷新 PostGIS 同步状态
      if (databaseInfo.value?.postgis_enabled) {
        loadPostgisSyncStatus()
      }
    } else {
      // 继续轮询
      datavPollingTimer = setTimeout(pollDatavImportProgress, 1000)
    }
  } catch (error: any) {
    console.error('获取导入进度失败:', error)
    datavPollingTimer = setTimeout(pollDatavImportProgress, 2000)
  }
}

// 处理上传文件选择
function handleDatavUploadChange(file: any) {
  datavUploadFile.value = file.raw
}

// 清理 DataV 导入轮询
function cleanupDatavPolling() {
  if (datavPollingTimer) {
    clearTimeout(datavPollingTimer)
    datavPollingTimer = null
  }
}

// 加载用户列表
async function loadUsers() {
  loadingUsers.value = true
  try {
    const response = await adminApi.getUsers({
      page: usersCurrentPage.value,
      page_size: usersPageSize.value,
      search: userSearchQuery.value || undefined,
      sort_by: userSortBy.value,
      sort_order: userSortOrder.value,
      roles: userRoleFilters.value.length === 2 ? undefined : userRoleFilters.value,
      statuses: userStatusFilters.value.length === 2 ? undefined : userStatusFilters.value,
    })
    if (!isMounted.value) return
    users.value = response.items
    usersTotal.value = response.total
    // 统计管理员数量
    adminCount.value = response.items.filter((u: User) => u.is_admin).length
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingUsers.value = false
    }
  }
}

// 立即加载用户（用于筛选，无需防抖）
function loadUsersImmediate() {
  usersCurrentPage.value = 1  // 筛选时重置到第一页
  loadUsers()
}

// 判断是否有激活的筛选条件
const hasActiveFilters = computed(() => {
  const roleFilterActive = userRoleFilters.value.length !== 2
  const statusFilterActive = userStatusFilters.value.length !== 1 || userStatusFilters.value[0] !== 'active'
  return roleFilterActive || statusFilterActive
})

// 用户搜索防抖
let userSearchTimeout: ReturnType<typeof setTimeout> | null = null
function handleUserSearch() {
  if (userSearchTimeout) {
    clearTimeout(userSearchTimeout)
  }
  userSearchTimeout = setTimeout(() => {
    usersCurrentPage.value = 1  // 搜索时重置到第一页
    loadUsers()
  }, 500)
}

// 用户排序点击
function handleUserSortClick(value: string) {
  if (userSortBy.value === value) {
    // 点击当前排序字段，切换排序方向
    userSortOrder.value = userSortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    // 切换到新的排序字段
    userSortBy.value = value
    // 对于创建时间和用户名，使用 desc（倒序，最新/字母序）
    // 对于邮箱，使用 asc（正序，字母序）
    userSortOrder.value = value === 'email' ? 'asc' : 'desc'
  }
  loadUsers()
}

// 重置筛选
function resetFilters() {
  userRoleFilters.value = ['admin', 'user']
  userStatusFilters.value = ['active']
  loadUsersImmediate()
}

// 重置筛选并关闭 popover（需要手动触发 DOM 事件）
function resetFiltersAndClose() {
  resetFilters()
  // 点击页面其他地方来关闭 popover
  document.dispatchEvent(new MouseEvent('click'))
}

// 判断是否为当前用户
function isCurrentUser(user: User): boolean {
  return authStore.user?.id === user.id
}

// 判断是否为第一位用户（ID 最小的用户）
function isFirstUser(user: User): boolean {
  if (users.value.length === 0) return false
  const firstUser = users.value.reduce((min: User | null, u: User) =>
    !min || u.id < min.id ? u : min
    , null)
  return firstUser?.id === user.id
}

// 切换用户管理员状态
async function toggleUserAdmin(user: User) {
  // 检查：如果要取消管理员身份，确保至少还有一位管理员
  if (user.is_admin && adminCount.value <= 1) {
    ElMessage.warning('系统至少需要保留一位管理员')
    return
  }
  try {
    await adminApi.updateUser(user.id, { is_admin: !user.is_admin })
    ElMessage.success('操作成功')
    await loadUsers()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 切换用户启用状态
async function toggleUserActive(user: User) {
  const action = user.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}用户 "${user.username}" 吗？`, '确认操作', {
      type: 'warning',
    })
    await adminApi.updateUser(user.id, { is_active: !user.is_active })
    ElMessage.success('操作成功')
    await loadUsers()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 删除用户
async function deleteUser(user: User) {
  try {
    await ElMessageBox.confirm(`确定要删除用户 "${user.username}" 吗？此操作不可撤销。`, '确认删除', {
      type: 'warning',
    })
    await adminApi.deleteUser(user.id)
    ElMessage.success('删除成功')
    await loadUsers()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 显示重置密码对话框
function showResetPasswordDialog(user: User) {
  resetPasswordForm.user_id = user.id
  resetPasswordForm.username = user.username
  resetPasswordForm.new_password = ''
  resetPasswordForm.confirm_password = ''
  resetPasswordDialogVisible.value = true
}

// 确认重置密码
async function confirmResetPassword() {
  // 验证密码
  if (!resetPasswordForm.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (resetPasswordForm.new_password.length < 6) {
    ElMessage.warning('密码长度至少为 6 位')
    return
  }
  if (resetPasswordForm.new_password !== resetPasswordForm.confirm_password) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  resettingPassword.value = true
  try {
    // 前端先对密码进行 SHA256 加密，与登录流程保持一致
    const hashedPassword = await hashPassword(resetPasswordForm.new_password)
    await adminApi.resetPassword(resetPasswordForm.user_id, hashedPassword)
    ElMessage.success('密码重置成功')
    resetPasswordDialogVisible.value = false
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    resettingPassword.value = false
  }
}

// 加载邀请码列表
async function loadInviteCodes() {
  loadingInviteCodes.value = true
  try {
    const response = await adminApi.getInviteCodes({
      page: inviteCodesCurrentPage.value,
      page_size: inviteCodesPageSize.value,
    })
    if (!isMounted.value) return
    inviteCodes.value = response.items
    inviteCodesTotal.value = response.total
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingInviteCodes.value = false
    }
  }
}

// 显示创建邀请码对话框
function showCreateInviteCodeDialog() {
  inviteCodeForm.code = ''
  inviteCodeForm.max_uses = 1
  inviteCodeForm.expires_in_days = undefined
  createInviteCodeDialogVisible.value = true
}

// 创建邀请码
async function createInviteCode() {
  creatingInviteCode.value = true
  try {
    await adminApi.createInviteCode({
      code: inviteCodeForm.code || undefined,
      max_uses: inviteCodeForm.max_uses,
      expires_in_days: inviteCodeForm.expires_in_days,
    })
    ElMessage.success('邀请码创建成功')
    createInviteCodeDialogVisible.value = false
    await loadInviteCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    creatingInviteCode.value = false
  }
}

// 删除邀请码
async function deleteInviteCode(inviteCode: InviteCode) {
  try {
    await ElMessageBox.confirm(`确定要删除邀请码 "${inviteCode.code}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await adminApi.deleteInviteCode(inviteCode.id)
    ElMessage.success('删除成功')
    await loadInviteCodes()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 获取邀请码状态
function getInviteCodeStatus(inviteCode: InviteCode) {
  if (!inviteCode.is_valid) {
    return { type: 'info', text: '已删除' }
  }
  if (inviteCode.expires_at && new Date(inviteCode.expires_at) < new Date()) {
    return { type: 'danger', text: '已过期' }
  }
  if (inviteCode.used_count >= inviteCode.max_uses) {
    return { type: 'warning', text: '已用完' }
  }
  return { type: 'success', text: '可用' }
}

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
  } else if (command === 'tracks') {
    router.push('/tracks')
  }
}

// 格式化文件大小
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// ========== 字体管理 ==========

// 加载字体列表
async function loadFonts() {
  loadingFonts.value = true
  try {
    const response = await adminApi.getFonts()
    if (!isMounted.value) return
    fonts.value = response.fonts
    activeFonts.value = response.active_fonts
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingFonts.value = false
    }
  }
}

// 设置激活字体
async function setActiveFont(fontType: 'a' | 'b' | 'c', filename: string) {
  try {
    await adminApi.setActiveFont(fontType, filename)
    activeFonts.value[`font_${fontType}`] = filename
    // 刷新配置，使主页能及时更新按钮显示状态
    await configStore.refreshConfig()
    ElMessage.success('字体设置成功')
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 处理字体上传
async function handleFontUpload(file: any) {
  const rawFile = file.raw
  if (!rawFile) return

  uploadingFont.value = true
  try {
    await adminApi.uploadFont(rawFile)
    ElMessage.success('字体上传成功')
    await loadFonts()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    uploadingFont.value = false
  }
}

// 删除字体
async function deleteFont(font: FontInfo) {
  try {
    await ElMessageBox.confirm(`确定要删除字体 "${font.filename}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await adminApi.deleteFont(font.filename)
    ElMessage.success('删除成功')
    await loadFonts()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// ========== 特殊地名映射管理 ==========

// 加载特殊地名映射
async function loadMappings() {
  loadingMapping.value = true
  try {
    const response = await adminApi.getSpecialPlaceMapping()
    if (!isMounted.value) return
    // 直接使用后端返回的原始 YAML 内容，保留注释和格式
    mappingYaml.value = response.raw_yaml
    mappingStats.value = { total: response.total }
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loadingMapping.value = false
    }
  }
}

// 从 YAML 保存映射表
async function saveMappingsFromYaml() {
  savingMapping.value = true
  try {
    // 直接发送原始 YAML 内容，保留注释和格式
    await adminApi.updateSpecialPlaceMapping({ yaml_content: mappingYaml.value })
    // 解析 YAML 以获取条目数量
    const mappings: Record<string, string> = {}
    const lines = mappingYaml.value.split('\n')
    for (const line of lines) {
      const trimmed = line.trim()
      // 跳过注释和空行
      if (!trimmed || trimmed.startsWith('#')) continue
      // 解析 key: value
      const colonIndex = trimmed.indexOf(':')
      if (colonIndex > 0) {
        const key = trimmed.substring(0, colonIndex).trim()
        const value = trimmed.substring(colonIndex + 1).trim()
        if (key && value) {
          mappings[key] = value
        }
      }
    }
    mappingStats.value = { total: Object.keys(mappings).length }
    ElMessage.success(`映射表保存成功，共 ${Object.keys(mappings).length} 条`)

    // 自动重新生成英文名称
    await regenerateNameEnInternal()
  } catch (error) {
    ElMessage.error('保存失败，请检查 YAML 格式')
  } finally {
    savingMapping.value = false
  }
}

// 重新生成英文名称（内部调用，不显示确认对话框）
async function regenerateNameEnInternal() {
  try {
    regeneratingNameEn.value = true
    const response = await adminApi.regenerateNameEn()
    ElMessage.success(`${response.message}，共更新 ${response.stats.updated} 条记录`)
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    regeneratingNameEn.value = false
  }
}

// 重新生成英文名称（按钮触发，显示确认对话框）
async function regenerateNameEn() {
  try {
    await ElMessageBox.confirm(
      '确定要重新生成所有行政区划的英文名称吗？这将使用最新的特殊地名映射表。',
      '确认操作',
      { type: 'warning' }
    )
    await regenerateNameEnInternal()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 边界数据管理方法
function handleBoundsFileChange(file: any) {
  selectedBoundsFile.value = file.raw
  boundsImportTask.value = null
}

async function importBoundsData() {
  if (!selectedBoundsFile.value) return

  try {
    importingBounds.value = true
    const response = await adminApi.importBoundsData(selectedBoundsFile.value)
    // 开始轮询任务状态
    boundsImportTask.value = { id: response.task_id, status: 'running', progress: 0 }
    pollBoundsImportTask(response.task_id)
    ElMessage.success('文件上传成功，正在后台处理')
  } catch (error) {
    // 错误已在拦截器中处理
    importingBounds.value = false
  }
}

async function pollBoundsImportTask(taskId: number) {
  boundsImportPolling.value = true
  let completed = false

  while (!completed && boundsImportPolling.value && isMounted.value) {
    try {
      const task = await adminApi.getBoundsImportTask(taskId)
      boundsImportTask.value = task

      if (task.status === 'completed') {
        completed = true
        importingBounds.value = false
        boundsImportPolling.value = false
        selectedBoundsFile.value = null
        ElMessage.success(`边界数据导入完成: ${task.result_path}`)
        await loadBoundsStats()
      } else if (task.status === 'failed') {
        completed = true
        importingBounds.value = false
        boundsImportPolling.value = false
        ElMessage.error(`导入失败: ${task.error_message}`)
      }

      // 未完成则等待 2 秒后再次轮询
      if (!completed) {
        await new Promise(resolve => setTimeout(resolve, 2000))
      }
    } catch (error) {
      completed = true
      importingBounds.value = false
      boundsImportPolling.value = false
    }
  }
}

async function loadBoundsStats() {
  try {
    loadingBoundsStats.value = true
    boundsStats.value = await adminApi.getBoundsStats()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loadingBoundsStats.value = false
  }
}

function formatBoundsStats() {
  if (!boundsStats.value) return []

  // 固定排序顺序和中文名称映射
  const levelOrder = ['province', 'city', 'area']
  const levelNames: Record<string, string> = {
    province: '省级',
    city: '地级',
    area: '县级'
  }

  return Object.entries(boundsStats.value.by_level)
    .sort(([a]: [string, any], [b]: [string, any]) => {
      return levelOrder.indexOf(a) - levelOrder.indexOf(b)
    })
    .map(([level, data]: [string, any]) => ({
      level: levelNames[level] || level,
      total: data.total,
      with_bounds: data.with_bounds
    }))
}

// 监听 tab 切换，如果有未保存的配置更改则提示
watch(activeTab, async (newTab, oldTab) => {
  // 切换到边界数据 tab 时加载统计
  if (newTab === 'bounds-data' && !boundsStats.value) {
    loadBoundsStats()
  }

  if (oldTab === 'config' && hasUnsavedConfigChanges()) {
    const action = await showUnsavedChangesDialog()
    if (action === 'leave') {
      // 点击"离开"按钮，重置为原始配置
      if (originalConfig.value) {
        Object.assign(config, originalConfig.value)
        initGeocodingConfig()
        initMapLayers()
      }
    } else if (action === 'save') {
      // 点击"保存配置"按钮
      await saveConfig()
    } else {
      // 点击"取消"按钮，切回原来的 tab
      activeTab.value = oldTab
    }
  }
})

// 路由离开守卫
onBeforeRouteLeave(async (to, from, next) => {
  // 只有在系统配置 tab 且有未保存更改时才提示
  if (activeTab.value === 'config' && hasUnsavedConfigChanges()) {
    const action = await showUnsavedChangesDialog()
    if (action === 'leave') {
      next()
    } else if (action === 'save') {
      await saveConfig()
      next()
    } else {
      next(false)
    }
  } else {
    next()
  }
})

// 浏览器刷新/关闭提示
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (activeTab.value === 'config' && hasUnsavedConfigChanges()) {
    e.preventDefault()
    e.returnValue = '' // Chrome 需要设置 returnValue
    return ''
  }
}

onMounted(async () => {
  await loadConfig()
  await loadUsers()
  await loadInviteCodes()
  await loadFonts()
  await loadMappings()
  // 加载行政区划状态
  loadDivisionStatus()
  // 加载 PostGIS 同步状态
  loadPostgisSyncStatus()

  // 添加窗口大小监听
  window.addEventListener('resize', handleResize)
  // 添加浏览器刷新/关闭提示
  window.addEventListener('beforeunload', handleBeforeUnload)
})

// 组件即将卸载时设置标志
onBeforeUnmount(() => {
  isMounted.value = false
})

// 组件卸载时移除监听器
onUnmounted(() => {
  boundsImportPolling.value = false
  cleanupDatavPolling()
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('beforeunload', handleBeforeUnload)
  // 清理 PostGIS 同步定时器
  if (postgisSyncTimer) {
    clearInterval(postgisSyncTimer)
    postgisSyncTimer = null
  }
})
</script>

<style scoped>
.admin-container {
  height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
}

.admin-container>.el-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  width: 100%;
}

.el-header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  z-index: 100;
  width: 100%;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}

.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
}

.header-content h1 {
  font-size: 20px;
  margin: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
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

.main {
  flex: 1;
  min-height: 0;
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* 标签页容器固定高度 */
.main>.el-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  overflow-x: hidden;
  width: 100%;
}

.main :deep(.el-tabs__header) {
  flex-shrink: 0;
  overflow: hidden;
}

.main :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  overflow-x: hidden;
}

.main :deep(.el-tab-pane) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overflow-x: hidden;
}

/* 系统配置 tab 可滚动 */
.config-tab-content {
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
}

/* 字体管理 tab 可滚动 */
.fonts-tab-content {
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
}

/* 列表卡片固定高度，内部滚动 */
.list-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overflow-x: hidden;
}

.list-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
}

/* 用户筛选卡片 */
.filter-card {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.filter-card :deep(.el-card__body) {
  padding: 12px;
}

.sort-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.sort-buttons .el-button {
  flex-shrink: 0;
}

.sort-icon {
  margin-left: 4px;
}

.filter-buttons {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.filter-label {
  margin-right: 12px;
  font-weight: 500;
  color: #606266;
}

:deep(.el-checkbox-button) {
  margin-right: 8px;
}

:deep(.el-dropdown-menu__item) {
  padding: 8px 12px;
}

:deep(.el-dropdown-menu) {
  min-width: 200px;
}

/* Popover 筛选样式 */
.filter-popover-content {
  padding: 8px 0;
}

.filter-section {
  padding: 4px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-section .filter-label {
  font-weight: 500;
  color: #606266;
  font-size: 14px;
}

.filter-section .el-checkbox-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-actions {
  padding: 4px 12px;
}

/* PC 端表格样式 */
.pc-table {
  width: 100%;
}

/* 分页器样式 */
.pagination {
  flex-shrink: 0;
  padding: 12px 0;
  display: flex;
  justify-content: center;
  overflow: hidden;
}

.pagination :deep(.el-pagination) {
  flex-wrap: wrap;
  justify-content: center;
}

.form-section {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #ebeef5;
}

.form-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 20px;
  padding-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.section-tip {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.section-description {
  font-size: 12px;
  color: #909399;
  margin-bottom: 16px;
  line-height: 1.6;
}

.section-description p {
  margin: 0;
  padding: 0;
}

.form-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.radio-hint {
  display: block;
  width: 100%;
  margin-top: 8px;
  margin-left: 0;
  line-height: 1.5;
}

.radio-hint a {
  font-size: inherit;
  font-weight: inherit;
  vertical-align: baseline;
}

/* DataV GeoJSON 行政区划导入 */
.datav-import-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.province-selector {
  margin-top: 4px;
}

.force-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-hint-inline, .radio-hint {
  font-size: 12px;
  color: #909399;
}

.import-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.import-progress {
  margin-top: 8px;
}

.progress-text {
  margin-top: 4px;
  font-size: 12px;
  color: #606266;
}

.error-text {
  color: var(--el-color-error);
}

.division-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #606266;
  padding: 8px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
}

.status-label {
  font-weight: 500;
}

.status-sep {
  color: #c0c4cc;
  margin: 0 4px;
}

/* 行政区划统计样式 */
.division-stats {
  padding: 10px 0;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.stat-row:last-child {
  border-bottom: none;
}

.stat-label {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.stat-value {
  font-weight: bold;
  color: var(--el-color-primary);
}

.stats-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background-color: var(--el-color-error-light-9);
  border-radius: 4px;
  color: var(--el-color-error);
}

.missing-codes {
  margin-top: 16px;
  padding: 12px;
  background-color: var(--el-color-warning-light-9);
  border-radius: 4px;
}

.missing-title {
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--el-color-warning);
}

.missing-item {
  font-size: 12px;
  padding: 4px 0;
  color: var(--el-text-color-regular);
  font-family: monospace;
}

.postgis-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: #f4f4f5;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.postgis-notice .el-icon {
  color: #409eff;
  flex-shrink: 0;
}

.postgis-notice a {
  color: #409eff;
  text-decoration: none;
}

.postgis-notice a:hover {
  text-decoration: underline;
}

/* PostGIS 同步状态 */
.postgis-sync-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
  font-size: 13px;
}

.postgis-sync-status {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sync-status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.sync-status-item .status-label {
  color: #606266;
}

.sync-status-item .status-value {
  font-weight: 500;
  color: #303133;
}

.sync-status-item.need-sync .status-value {
  color: #e6a23c;
  font-weight: 600;
}

.sync-progress {
  margin-top: 8px;
}

.sync-progress .progress-text {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.map-layers-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.map-layer-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  transition: background-color 0.2s;
  cursor: grab;
}

.map-layer-item:active {
  cursor: grabbing;
}

.map-layer-item:hover {
  background: #ecf5ff;
}

.map-layer-item.is-default {
  background: #f0f9ff;
  border: 1px solid #b3d8ff;
}

/* 主行布局（桌面端） */
.map-layer-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.layer-info {
  flex: 1;
  min-width: 0;
}

.layer-info :deep(.el-radio) {
  margin: 0;
}

.layer-info :deep(.el-radio__label) {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.layer-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.layer-id {
  font-size: 12px;
  color: #909399;
}

.layer-status {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

/* 配置输入框区域 */
.map-layer-config {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 30px;
}

.config-input {
  flex: 1;
  min-width: 200px;
}

/* 拖拽手柄 */
.drag-handle {
  cursor: grab;
  color: #909399;
  font-size: 18px;
  flex-shrink: 0;
}

.drag-handle:active {
  cursor: grabbing;
}

/* 移动端排序按钮 */
.mobile-sort-buttons {
  display: none;
  flex-direction: column;
  gap: 2px;
  flex-shrink: 0;
}

.mobile-sort-buttons .el-button {
  padding: 4px;
}

/* vuedraggable 拖拽时的样式 */
.map-layers-list :deep(.sortable-ghost) {
  opacity: 0.5;
  background: #ecf5ff;
}

.map-layers-list :deep(.sortable-drag) {
  opacity: 0.8;
}

/* 默认隐藏桌面端专用元素 */
.desktop-only {
  display: none;
}

/* 默认显示移动端专用元素 */
.mobile-only {
  display: inline;
}

/* 边界数据管理样式 */
.bounds-data-tab-content {
  overflow-y: auto;
  display: block !important;
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .admin-container {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    overflow: hidden;
    background: #f5f7fa;
    width: 100vw;
  }

  .admin-container>.el-container {
    height: 100%;
    width: 100%;
  }

  .el-header {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 100;
    width: 100%;
    overflow: hidden;
  }

  .main {
    padding-top: 70px;
    padding-bottom: 0;
    padding-left: 0;
    padding-right: 0;
    width: 100%;
    box-sizing: border-box;
  }

  .main>.el-tabs {
    width: 100%;
    overflow-x: hidden;
  }

  /* 确保标签页内容可以滚动 */
  .main>.el-tabs>.el-tabs__content {
    overflow: visible;
  }

  .el-tab-pane {
    overflow: visible;
  }

  .header-content h1 {
    font-size: 16px;
    min-width: 0;
  }

  /* 筛选卡片移动端样式 */
  .filter-card {
    margin-bottom: 8px;
  }

  /* 搜索框和按钮之间的间距 */
  .filter-card .el-row .el-col:nth-child(2),
  .filter-card .el-row .el-col:nth-child(3) {
    margin-top: 8px;
  }

  /* Popover 筛选移动端样式 */
  .filter-popover-content {
    padding: 4px 0;
  }

  .filter-section {
    padding: 4px 8px;
  }

  .filter-section .filter-label {
    font-size: 13px;
  }

  .filter-actions {
    padding: 4px 8px;
  }

  .filter-card :deep(.el-card__body) {
    padding: 8px;
  }

  .sort-buttons {
    gap: 4px;
    flex-wrap: nowrap;
  }

  .sort-buttons .el-button {
    font-size: 11px;
    padding: 5px 8px;
  }

  /* 隐藏 PC 端表格，显示移动端卡片 */
  .pc-table {
    display: none !important;
  }

  .mobile-card-list {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 10px;
    /* 为固定底部的分页器留出空间 */
    padding-bottom: 70px;
  }

  /* 移动端列表卡片 */
  .list-card {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
    margin: 0;
    border: none;
    box-shadow: none;
    background: transparent;
  }

  .list-card :deep(.el-card__body) {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
    padding: 0;
  }

  /* 分页器固定在底部 */
  .pagination {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 100;
    background: #f5f7fa;
    padding: 10px;
    padding-bottom: max(10px, env(safe-area-inset-bottom));
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
    margin-top: 0;
    overflow: hidden;
  }

  .pagination :deep(.el-pagination) {
    justify-content: center;
  }

  /* 系统配置 tab 可滚动 */
  .config-tab-content {
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 10px;
  }

  /* 表单项上下布局 */
  :deep(.config-form .el-form-item) {
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-start !important;
  }

  :deep(.config-form .el-form-item__label-wrap) {
    margin-left: 0 !important;
  }

  :deep(.config-form .el-form-item__label) {
    width: auto !important;
    min-width: auto !important;
    text-align: left !important;
    margin-bottom: 8px;
    flex-shrink: 0;
    justify-content: flex-start !important;
  }

  :deep(.config-form .el-form-item__content) {
    margin-left: 0 !important;
    width: 100% !important;
    text-align: left !important;
  }

  /* 地图设置区域移动端优化 */
  .map-layer-config {
    padding-left: 0;
    flex-direction: column;
  }

  .config-input {
    min-width: 100%;
  }

  .map-layer-main {
    flex-wrap: nowrap;
    align-items: flex-start;
  }

  .layer-info {
    flex: 1;
    min-width: 0;
    margin: 0;
    padding: 0;
  }

  .layer-info :deep(.el-radio) {
    align-items: center;
    height: 32px;
    display: inline-flex;
    margin: 0 !important;
  }

  .layer-info :deep(.el-radio__input) {
    margin: 0;
  }

  .layer-info :deep(.el-radio__label) {
    align-items: center;
    line-height: 32px;
    padding-left: 8px;
    margin: 0 !important;
  }

  /* 移动端隐藏拖拽手柄，显示排序按钮 */
  .drag-handle {
    display: none;
  }

  .mobile-sort-buttons {
    display: flex;
    height: 32px;
  }

  .mobile-sort-buttons :deep(.el-button) {
    margin: 0;
  }

  .map-layer-main :deep(.el-switch) {
    flex-shrink: 0;
    align-self: center;
    height: 32px;
  }

  /* 全局重置移动端单选框 margin-right */
  :deep(.el-radio) {
    margin-right: 0 !important;
  }

  .layer-status {
    flex-shrink: 0;
    align-self: center;
  }

  /* 地理编码设置 - 单选按钮垂直排列 */
  :deep(.el-radio-group) {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }

  /* 表格隐藏，使用移动端卡片列表 */
  .el-table {
    display: none;
  }

  /* 边界数据统计表格在移动端仍然显示 */
  .bounds-stats .el-table {
    display: block !important;
  }

  /* 移动端卡片列表样式 */
  .mobile-card-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .mobile-user-card,
  .mobile-invite-card {
    background: white;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .mobile-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid #ebeef5;
  }

  .mobile-card-title {
    font-weight: 500;
    font-size: 16px;
    color: #303133;
  }

  .mobile-card-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 14px;
  }

  .mobile-card-row {
    display: flex;
    justify-content: space-between;
  }

  .mobile-card-label {
    color: #909399;
  }

  .mobile-card-value {
    color: #303133;
    text-align: right;
  }

  .mobile-card-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #ebeef5;
  }

  .mobile-card-actions .el-button {
    flex: 1;
  }

  /* 邀请码卡片特殊样式 */
  .invite-code-display {
    font-family: monospace;
    font-size: 16px;
    background: #f5f7fa;
    padding: 8px 12px;
    border-radius: 4px;
  }
}

/* 桌面端隐藏移动端卡片 */
@media (min-width: 1367px) {
  .mobile-card-list {
    display: none !important;
  }

  .pc-table {
    display: table !important;
  }

  .desktop-only {
    display: inline;
  }

  .mobile-only {
    display: none;
  }

  .pagination {
    position: static;
    box-shadow: none;
    padding: 12px 0;
  }
}

/* ========== 桌面端默认样式 ========== */

/* 字体选择器样式 */
.font-selector-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.font-selector-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.font-selector-desc {
  font-size: 12px;
  color: #909399;
  margin-top: -4px;
  margin-bottom: 4px;
}

/* 标题栏带操作按钮（桌面端） */
.card-header-with-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.card-header-with-actions>span {
  flex-shrink: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: nowrap;
}

/* 特殊地名映射样式（桌面端） */
.place-mapping-tab-content {
  height: 100%;
  overflow: hidden;
}

.place-mapping-tab-content .el-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.place-mapping-tab-content .el-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.place-mapping-tab-content .el-card :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.mapping-description {
  padding: 10px 12px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.mapping-description p {
  margin: 4px 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.mapping-description code {
  padding: 2px 6px;
  background-color: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 3px;
  font-family: monospace;
  color: var(--el-color-primary);
}

.mapping-description-error {
  color: var(--el-color-danger);
  font-weight: 500;
}

/* 编辑器容器（桌面端） */
.mapping-editor-wrapper {
  flex: 1;
  min-height: 300px;
  display: flex;
  flex-direction: column;
  /* 确保不超过父容器 */
  max-height: 100%;
}

/* CodeMirror 编辑器占满容器 */
.mapping-editor-wrapper :deep(.codemirror-yaml-editor) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}

/* CodeMirror 根元素高度限制 */
.mapping-editor-wrapper :deep(.cm-editor) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 100%;
  overflow: hidden;
}

/* CodeMirror 编辑器滚动 */
.mapping-editor-wrapper :deep(.cm-scroller) {
  flex: 1;
  overflow: auto;
  min-height: 0;
  max-height: 100%;
  box-sizing: border-box;
}

/* 边界数据管理样式（桌面端） */
.bounds-data-tab-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.bounds-upload {
  margin-bottom: 20px;
}

.bounds-upload :deep(.el-upload-dragger) {
  padding: 40px;
}

.selected-file-info {
  margin-top: 20px;
  padding: 16px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
}

.import-result {
  margin-top: 20px;
}

.import-result .text-error {
  color: var(--el-color-danger);
}

.import-progress {
  margin-top: 20px;
  padding: 16px;
  border-radius: 4px;
}

.import-progress--pending,
.import-progress--running {
  background-color: var(--el-color-info-light-9);
}

.import-progress--completed {
  background-color: var(--el-color-success-light-9);
}

.import-progress--failed {
  background-color: var(--el-color-danger-light-9);
}

.result-summary {
  margin-top: 12px;
  color: var(--el-color-success);
  font-size: 14px;
  line-height: 1.5;
}

.error-message {
  margin-top: 12px;
  color: var(--el-color-danger);
  font-size: 14px;
  line-height: 1.5;
}

.error-details {
  margin-top: 12px;
}

.error-details h4 {
  margin-bottom: 8px;
  font-size: 14px;
}

.error-details ul {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--el-color-danger);
}

.error-details li {
  margin: 4px 0;
}

.bounds-stats-section {
  margin-top: 20px;
}

.bounds-stats-section h3 {
  margin-bottom: 12px;
  font-size: 16px;
}

.bounds-stats-section h4 {
  margin: 20px 0 12px 0;
  font-size: 14px;
}

/* 骨架屏样式 */
.config-skeleton {
  padding: 20px;
}

.list-skeleton {
  padding: 20px;
}

.fonts-skeleton {
  padding: 20px;
}

/* 未保存更改对话框样式 */
.unsaved-changes-dialog .dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.unsaved-changes-dialog p {
  margin: 0;
  font-size: 14px;
  color: #606266;
}

/* 可滚动内容（桌面端） */
.scrollable-content {
  overflow-y: auto;
  max-height: calc(100vh - 200px);
}

/* ========== 移动端样式覆盖 ========== */
@media (max-width: 1366px) {
  /* 字体选择器移动端 */
  .font-selector-item {
    margin-bottom: 12px;
  }

  /* 标题栏移动端 */
  .card-header-with-actions {
    gap: 12px;
  }

  .header-actions {
    gap: 6px;
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

  /* 特殊地名映射移动端 */
  .mapping-editor-wrapper {
    min-height: 400px;
    display: flex;
    flex-direction: column;
    /* 确保不超过父容器 */
    max-height: 100%;
  }

  .mapping-editor-wrapper :deep(.codemirror-yaml-editor) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    border: 1px solid var(--el-border-color);
    border-radius: 4px;
  }

  .mapping-editor-wrapper :deep(.cm-editor) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    max-height: 100%;
    overflow: hidden;
  }

  .mapping-editor-wrapper :deep(.cm-scroller) {
    flex: 1;
    overflow: auto;
    min-height: 0;
    /* 确保不超出容器 */
    max-height: 100%;
    box-sizing: border-box;
  }

  /* 边界数据标签页移动端 */
  .bounds-data-tab-content {
    display: block !important;
    gap: 16px;
  }

  .bounds-data-tab-content>.el-card {
    margin-bottom: 16px;
  }

  .bounds-upload :deep(.el-upload-dragger) {
    padding: 40px 20px;
  }

  /* 可滚动内容移动端 */
  .scrollable-content {
    max-height: none;
    min-height: calc(100vh - 140px);
    padding-bottom: 20px;
  }

  /* 边界数据统计移动端样式 */
  .bounds-stats-section {
    overflow-x: hidden;
  }

  .bounds-stats {
    min-width: 100%;
    display: block !important;
    width: 100% !important;
  }

  .bounds-stats h3,
  .bounds-stats h4 {
    font-size: 14px;
  }

  .bounds-stats .el-table {
    width: 100%;
  }

  .bounds-stats .el-table:before {
    display: none !important;
  }

  .bounds-stats .el-table__wrapper {
    width: 100% !important;
  }

  .bounds-stats .el-table__body-wrapper {
    overflow-x: hidden;
    width: 100% !important;
  }

  .bounds-stats .el-table__body {
    width: 100% !important;
  }

  .bounds-stats .el-table th,
  .bounds-stats .el-table td {
    padding: 6px 2px;
    word-break: break-word;
  }

  .bounds-stats .el-table .el-table__cell {
    padding: 6px 2px;
  }

  .bounds-stats .el-table .cell {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: normal;
    line-height: 1.4;
  }
}
</style>
